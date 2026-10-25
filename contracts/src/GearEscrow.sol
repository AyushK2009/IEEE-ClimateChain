// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {MerkleProof} from "@openzeppelin/contracts/utils/cryptography/MerkleProof.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title GearEscrow: net passports, deposits, a sponsor-funded bounty pool, and recovery payouts.
/// @notice Each net is an ERC-721 passport. Money moves between three buckets and the invariant
///         token.balanceOf(this) == depositsHeld + poolAvailable + poolReserved always holds:
///         - depositsHeld:  refundable deposits of active nets (never used for bounties)
///         - poolAvailable: sponsor money + forfeited deposits, not yet promised to a claim
///         - poolReserved:  bounties locked by pending claims
///         Off-chain services hold PRICER_ROLE (daily price lists, published as Merkle roots) and
///         VERIFIER_ROLE (claim outcomes). The chain cannot see the ocean; it enforces the money rules.
contract GearEscrow is ERC721, AccessControl, ReentrancyGuard {
    using SafeERC20 for IERC20;

    bytes32 public constant SUPPLIER_ROLE = keccak256("SUPPLIER_ROLE");
    bytes32 public constant PRICER_ROLE = keccak256("PRICER_ROLE");
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");

    enum Status { None, Active, Lost, ClaimPending, Recovered, Returned }
    enum Outcome { None, Accepted, Rejected, Flagged }

    struct Net {
        uint128 deposit;
        uint64 lostAt;
        Status status;
        bool unreported;        // recovered without a prior loss report (penalty record)
        bytes32 lossHash;       // hash of the exact loss report; coordinates stay off-chain
        uint256 openClaim;
    }

    struct Claim {
        uint256 netId;
        address claimant;
        uint128 bounty;
        uint64 epoch;
        uint64 submittedAt;
        bool fromDeposit;       // unreported recovery: paid from the owner's deposit
        Outcome outcome;
        bytes32 photoHash;      // fingerprint of the evidence photo
        bytes32 reportHash;     // fingerprint of the full verification report
    }

    IERC20 public immutable token;
    uint256 public depositsHeld;
    uint256 public poolAvailable;
    uint256 public poolReserved;
    uint256 public nextNetId = 1;
    uint256 public nextClaimId = 1;
    uint64 public currentEpoch;
    uint64 public constant FLAG_TIMEOUT = 3 days;

    mapping(uint256 => Net) public nets;
    mapping(uint256 => Claim) public claims;
    mapping(uint64 => bytes32) public epochRoot;
    mapping(uint64 => uint256) public epochTotal;

    event NetRegistered(uint256 indexed netId, address indexed owner, address indexed supplier, uint256 deposit);
    event NetLost(uint256 indexed netId, address indexed owner, bytes32 lossHash, uint256 depositToPool);
    event NetReturned(uint256 indexed netId, address indexed owner, uint256 refund);
    event Sponsored(address indexed sponsor, uint256 amount);
    event EpochPublished(uint64 indexed epoch, bytes32 root, uint256 totalAdvertised, string boardURI);
    event ClaimSubmitted(uint256 indexed claimId, uint256 indexed netId, address indexed claimant, uint256 bounty,
        uint64 epoch, bool fromDeposit, bytes32 photoHash);
    event ClaimResolved(uint256 indexed claimId, uint256 indexed netId, Outcome outcome, bytes32 reportHash, uint256 paid);

    error NotOwner();
    error BadStatus(Status status);
    error OwnerCannotClaim();
    error StaleEpoch();
    error BadProof();
    error InsufficientPool();
    error OverPromised();
    error BadOutcome();
    error TooEarly();
    error LengthMismatch();

    constructor(IERC20 token_, address admin) ERC721("Ghost Gear Passport", "GEAR") {
        token = token_;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
    }

    // ---------------------------------------------------------------- lifecycle

    /// @notice Supplier checkout: mint one passport per net and pull each net's deposit from the buyer
    ///         (the buyer approves this contract at checkout).
    function registerNets(address buyer, uint256 count, uint128 depositEach)
        external onlyRole(SUPPLIER_ROLE) nonReentrant returns (uint256 firstId)
    {
        uint256 total = count * depositEach;
        token.safeTransferFrom(buyer, address(this), total);
        depositsHeld += total;
        firstId = nextNetId;
        for (uint256 i = 0; i < count; i++) {
            uint256 id = nextNetId++;
            nets[id].deposit = depositEach;
            nets[id].status = Status.Active;
            _mint(buyer, id);
            emit NetRegistered(id, buyer, msg.sender, depositEach);
        }
    }

    /// @notice Owner reports nets lost. Each deposit is forfeited into the bounty pool.
    function reportLoss(uint256[] calldata ids, bytes32[] calldata lossHashes) external {
        if (ids.length != lossHashes.length) revert LengthMismatch();
        for (uint256 i = 0; i < ids.length; i++) {
            uint256 id = ids[i];
            if (ownerOf(id) != msg.sender) revert NotOwner();
            Net storage n = nets[id];
            if (n.status != Status.Active) revert BadStatus(n.status);
            n.status = Status.Lost;
            n.lostAt = uint64(block.timestamp);
            n.lossHash = lossHashes[i];
            depositsHeld -= n.deposit;
            poolAvailable += n.deposit;
            emit NetLost(id, msg.sender, lossHashes[i], n.deposit);
        }
    }

    /// @notice End-of-life take-back by the supplier: the owner gets the deposit back.
    function confirmReturn(uint256 id) external onlyRole(SUPPLIER_ROLE) nonReentrant {
        Net storage n = nets[id];
        if (n.status != Status.Active) revert BadStatus(n.status);
        n.status = Status.Returned;
        depositsHeld -= n.deposit;
        address owner = ownerOf(id);
        token.safeTransfer(owner, n.deposit);
        emit NetReturned(id, owner, n.deposit);
    }

    /// @notice Anyone can add money to the bounty pool. Sponsorship cannot be withdrawn.
    function sponsor(uint256 amount) external nonReentrant {
        token.safeTransferFrom(msg.sender, address(this), amount);
        poolAvailable += amount;
        emit Sponsored(msg.sender, amount);
    }

    // ---------------------------------------------------------------- pricing

    /// @notice Publish the fingerprint of today's full price list. Leaves are (netId, epoch, bounty).
    ///         The contract refuses lists that advertise more than the pool holds.
    function publishEpoch(bytes32 root, uint256 totalAdvertised, string calldata boardURI)
        external onlyRole(PRICER_ROLE)
    {
        if (totalAdvertised > poolAvailable) revert OverPromised();
        uint64 e = ++currentEpoch;
        epochRoot[e] = root;
        epochTotal[e] = totalAdvertised;
        emit EpochPublished(e, root, totalAdvertised, boardURI);
    }

    function leafOf(uint256 netId, uint64 epoch, uint128 bounty) public pure returns (bytes32) {
        return keccak256(bytes.concat(keccak256(abi.encode(netId, epoch, bounty))));
    }

    // ---------------------------------------------------------------- claims

    /// @notice Claim a recovered net. For a reported-lost net the advertised bounty is proven against
    ///         the current (or previous) epoch's root and locked. For an active net (no loss report)
    ///         the bounty is exactly the owner's deposit.
    function submitClaim(uint256 id, uint128 bounty, uint64 epoch, bytes32[] calldata proof, bytes32 photoHash)
        external nonReentrant returns (uint256 claimId)
    {
        if (msg.sender == ownerOf(id)) revert OwnerCannotClaim();
        Net storage n = nets[id];
        bool fromDeposit;
        if (n.status == Status.Lost) {
            if (epoch == 0 || (epoch != currentEpoch && epoch + 1 != currentEpoch)) revert StaleEpoch();
            if (!MerkleProof.verifyCalldata(proof, epochRoot[epoch], leafOf(id, epoch, bounty))) revert BadProof();
            if (bounty > poolAvailable) revert InsufficientPool();
            poolAvailable -= bounty;
        } else if (n.status == Status.Active) {
            bounty = n.deposit;
            depositsHeld -= bounty;
            fromDeposit = true;
            epoch = 0;
        } else {
            revert BadStatus(n.status);
        }
        poolReserved += bounty;
        claimId = nextClaimId++;
        claims[claimId] = Claim(id, msg.sender, bounty, epoch, uint64(block.timestamp), fromDeposit,
            Outcome.None, photoHash, bytes32(0));
        n.status = Status.ClaimPending;
        n.openClaim = claimId;
        emit ClaimSubmitted(claimId, id, msg.sender, bounty, epoch, fromDeposit, photoHash);
    }

    /// @notice Record the verification outcome. Accepted pays the locked bounty; Rejected releases it;
    ///         Flagged keeps it reserved until a later resolution or expireClaim.
    function resolveClaim(uint256 claimId, Outcome outcome, bytes32 reportHash)
        external onlyRole(VERIFIER_ROLE) nonReentrant
    {
        Claim storage c = claims[claimId];
        Net storage n = nets[c.netId];
        if (n.status != Status.ClaimPending || n.openClaim != claimId) revert BadStatus(n.status);
        if (outcome == Outcome.None) revert BadOutcome();
        c.outcome = outcome;
        c.reportHash = reportHash;
        uint256 paid;
        if (outcome == Outcome.Accepted) {
            poolReserved -= c.bounty;
            n.status = Status.Recovered;
            n.openClaim = 0;
            n.unreported = c.fromDeposit;
            paid = c.bounty;
            token.safeTransfer(c.claimant, c.bounty);
        } else if (outcome == Outcome.Rejected) {
            _release(c, n);
        }
        emit ClaimResolved(claimId, c.netId, outcome, reportHash, paid);
    }

    /// @notice Anyone can release a flagged claim that was not resolved within FLAG_TIMEOUT.
    function expireClaim(uint256 claimId) external {
        Claim storage c = claims[claimId];
        Net storage n = nets[c.netId];
        if (c.outcome != Outcome.Flagged || n.openClaim != claimId) revert BadOutcome();
        if (block.timestamp < c.submittedAt + FLAG_TIMEOUT) revert TooEarly();
        c.outcome = Outcome.Rejected;
        _release(c, n);
        emit ClaimResolved(claimId, c.netId, Outcome.Rejected, c.reportHash, 0);
    }

    function _release(Claim storage c, Net storage n) private {
        poolReserved -= c.bounty;
        if (c.fromDeposit) {
            depositsHeld += c.bounty;
            n.status = Status.Active;
        } else {
            poolAvailable += c.bounty;
            n.status = Status.Lost;
        }
        n.openClaim = 0;
    }

    // ---------------------------------------------------------------- views and plumbing

    function poolState() external view returns (uint256 balance, uint256 held, uint256 available, uint256 reserved) {
        return (token.balanceOf(address(this)), depositsHeld, poolAvailable, poolReserved);
    }

    /// @dev Passports can only change hands while the net is active (not while lost or under claim).
    function _update(address to, uint256 tokenId, address auth) internal override returns (address) {
        address from = _ownerOf(tokenId);
        if (from != address(0) && nets[tokenId].status != Status.Active) revert BadStatus(nets[tokenId].status);
        return super._update(to, tokenId, auth);
    }

    function supportsInterface(bytes4 id) public view override(ERC721, AccessControl) returns (bool) {
        return super.supportsInterface(id);
    }
}
