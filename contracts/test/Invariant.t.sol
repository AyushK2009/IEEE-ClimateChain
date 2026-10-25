// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {GearEscrow} from "../src/GearEscrow.sol";
import {DemoUSD} from "../src/DemoUSD.sol";

/// Drives random sequences of real lifecycle actions against the escrow.
contract Handler is Test {
    GearEscrow public esc;
    DemoUSD public usd;
    address supplier; address oracle; address fleet; address crew; address fund;
    uint256[] public openClaims;
    uint256 public ghostReserved;
    uint256 lastPricedNet; uint128 lastPrice; uint64 lastEpoch;

    constructor(GearEscrow e, DemoUSD u, address s, address o, address f, address c, address fd) {
        esc = e; usd = u; supplier = s; oracle = o; fleet = f; crew = c; fund = fd;
    }

    function _net(uint256 seed) internal view returns (uint256) {
        uint256 n = esc.nextNetId() - 1;
        return n == 0 ? 0 : 1 + seed % n;
    }

    function _status(uint256 id) internal view returns (GearEscrow.Status s) { (,, s,,,) = esc.nets(id); }

    function register(uint256 count) external {
        count = bound(count, 1, 3);
        vm.prank(supplier); esc.registerNets(fleet, count, 200e18);
    }

    function lose(uint256 seed) external {
        uint256 id = _net(seed);
        if (id == 0 || _status(id) != GearEscrow.Status.Active) return;
        uint256[] memory ids = new uint256[](1); ids[0] = id;
        bytes32[] memory hs = new bytes32[](1);
        vm.prank(fleet); esc.reportLoss(ids, hs);
    }

    function sponsor(uint256 amt) external {
        amt = bound(amt, 1e18, 2_000e18);
        vm.prank(fund); esc.sponsor(amt);
    }

    function publish(uint256 seed, uint256 price) external {
        uint256 id = _net(seed);
        if (id == 0 || _status(id) != GearEscrow.Status.Lost || esc.poolAvailable() == 0) return;
        uint128 p = uint128(bound(price, 1, esc.poolAvailable()));
        uint64 e = esc.currentEpoch() + 1;
        bytes32 root = esc.leafOf(id, e, p);
        vm.prank(oracle); esc.publishEpoch(root, p, "");
        (lastPricedNet, lastPrice, lastEpoch) = (id, p, e);
    }

    function claimPriced() external {
        if (lastPricedNet == 0 || _status(lastPricedNet) != GearEscrow.Status.Lost) return;
        vm.prank(crew);
        try esc.submitClaim(lastPricedNet, lastPrice, lastEpoch, new bytes32[](0), bytes32(0)) returns (uint256 c) {
            openClaims.push(c); ghostReserved += lastPrice;
        } catch {}
    }

    function claimUnreported(uint256 seed) external {
        uint256 id = _net(seed);
        if (id == 0 || _status(id) != GearEscrow.Status.Active) return;
        vm.prank(crew); uint256 c = esc.submitClaim(id, 0, 0, new bytes32[](0), bytes32(0));
        (,, uint128 b,,,,,,) = esc.claims(c);
        openClaims.push(c); ghostReserved += b;
    }

    function resolve(uint256 seed, uint8 o) external {
        if (openClaims.length == 0) return;
        uint256 k = seed % openClaims.length;
        uint256 c = openClaims[k];
        GearEscrow.Outcome out = GearEscrow.Outcome(1 + o % 3);
        vm.prank(oracle); esc.resolveClaim(c, out, bytes32(0));
        if (out != GearEscrow.Outcome.Flagged) {
            (,, uint128 b,,,,,,) = esc.claims(c);
            ghostReserved -= b;
            openClaims[k] = openClaims[openClaims.length - 1]; openClaims.pop();
        }
    }

    function giveBack(uint256 seed) external {
        uint256 id = _net(seed);
        if (id == 0 || _status(id) != GearEscrow.Status.Active) return;
        vm.prank(supplier); esc.confirmReturn(id);
    }
}

contract InvariantTest is Test {
    GearEscrow esc; DemoUSD usd; Handler h;

    function setUp() public {
        address admin = makeAddr("admin"); address s = makeAddr("s"); address o = makeAddr("o");
        address f = makeAddr("f"); address c = makeAddr("c"); address fd = makeAddr("fd");
        vm.startPrank(admin);
        usd = new DemoUSD(admin);
        esc = new GearEscrow(usd, admin);
        esc.grantRole(esc.SUPPLIER_ROLE(), s);
        esc.grantRole(esc.PRICER_ROLE(), o);
        esc.grantRole(esc.VERIFIER_ROLE(), o);
        usd.mint(f, 1e30); usd.mint(fd, 1e30);
        vm.stopPrank();
        vm.prank(f); usd.approve(address(esc), type(uint256).max);
        vm.prank(fd); usd.approve(address(esc), type(uint256).max);
        h = new Handler(esc, usd, s, o, f, c, fd);
        targetContract(address(h));
    }

    /// Money always adds up: nothing is created, lost, or double-counted.
    function invariant_BooksBalance() public view {
        (uint256 bal, uint256 held, uint256 avail, uint256 res) = esc.poolState();
        assertEq(bal, held + avail + res);
    }

    /// Reserved money equals exactly the bounties of claims still pending.
    function invariant_ReservedMatchesOpenClaims() public view {
        assertEq(esc.poolReserved(), h.ghostReserved());
    }
}
