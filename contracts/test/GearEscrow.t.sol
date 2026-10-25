// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test, stdJson} from "forge-std/Test.sol";
import {GearEscrow} from "../src/GearEscrow.sol";
import {DemoUSD} from "../src/DemoUSD.sol";

contract GearEscrowTest is Test {
    using stdJson for string;

    DemoUSD usd;
    GearEscrow esc;
    address admin = makeAddr("admin");
    address supplier = makeAddr("supplier");
    address oracle = makeAddr("oracle");
    address fleet = makeAddr("fleet");
    address crew = makeAddr("crew");
    address fund = makeAddr("fund");
    uint128 constant DEP = 200e18;

    function setUp() public {
        vm.startPrank(admin);
        usd = new DemoUSD(admin);
        esc = new GearEscrow(usd, admin);
        esc.grantRole(esc.SUPPLIER_ROLE(), supplier);
        esc.grantRole(esc.PRICER_ROLE(), oracle);
        esc.grantRole(esc.VERIFIER_ROLE(), oracle);
        usd.mint(fleet, 10_000e18);
        usd.mint(fund, 100_000e18);
        vm.stopPrank();
        vm.prank(fleet); usd.approve(address(esc), type(uint256).max);
        vm.prank(fund); usd.approve(address(esc), type(uint256).max);
    }

    function _buy(uint256 n) internal returns (uint256 first) {
        vm.prank(supplier);
        first = esc.registerNets(fleet, n, DEP);
    }

    function _lose(uint256 id) internal {
        uint256[] memory ids = new uint256[](1); ids[0] = id;
        bytes32[] memory hs = new bytes32[](1); hs[0] = keccak256("loss");
        vm.prank(fleet); esc.reportLoss(ids, hs);
    }

    function _publishSingle(uint256 id, uint128 bounty) internal returns (uint64 e) {
        e = esc.currentEpoch() + 1;
        bytes32 root = esc.leafOf(id, e, bounty);
        vm.prank(oracle); esc.publishEpoch(root, bounty, "board");
    }

    function _status(uint256 id) internal view returns (GearEscrow.Status s) {
        (,, s,,,) = esc.nets(id);
    }

    function _assertBooks() internal view {
        (uint256 bal, uint256 held, uint256 avail, uint256 res) = esc.poolState();
        assertEq(bal, held + avail + res, "books must balance");
    }

    function test_RegisterMintsPassportsAndHoldsDeposits() public {
        uint256 first = _buy(3);
        assertEq(first, 1);
        assertEq(esc.ownerOf(3), fleet);
        assertEq(esc.depositsHeld(), 3 * DEP);
        assertEq(uint8(_status(2)), uint8(GearEscrow.Status.Active));
        _assertBooks();
    }

    function test_ReportLossMovesDepositToPool() public {
        _buy(2); _lose(1);
        assertEq(esc.depositsHeld(), DEP);
        assertEq(esc.poolAvailable(), DEP);
        assertEq(uint8(_status(1)), uint8(GearEscrow.Status.Lost));
        _assertBooks();
    }

    function test_FullLoopLockAndPay() public {
        _buy(1); _lose(1);
        vm.prank(fund); esc.sponsor(5_000e18);
        uint128 bounty = 750e18;
        uint64 e = _publishSingle(1, bounty);
        vm.prank(crew);
        uint256 cid = esc.submitClaim(1, bounty, e, new bytes32[](0), keccak256("photo"));
        assertEq(esc.poolReserved(), bounty, "bounty locked");
        // a later, higher price list does not change the locked claim
        vm.prank(oracle); esc.publishEpoch(bytes32(uint256(1)), 0, "next day");
        vm.prank(oracle); esc.resolveClaim(cid, GearEscrow.Outcome.Accepted, keccak256("report"));
        assertEq(usd.balanceOf(crew), bounty);
        assertEq(uint8(_status(1)), uint8(GearEscrow.Status.Recovered));
        assertEq(esc.poolReserved(), 0);
        _assertBooks();
    }

    function test_CannotPayTwice() public {
        _buy(1); _lose(1);
        vm.prank(fund); esc.sponsor(5_000e18);
        uint64 e = _publishSingle(1, 300e18);
        vm.prank(crew); uint256 cid = esc.submitClaim(1, 300e18, e, new bytes32[](0), bytes32(0));
        vm.prank(oracle); esc.resolveClaim(cid, GearEscrow.Outcome.Accepted, bytes32(0));
        vm.expectRevert(abi.encodeWithSelector(GearEscrow.BadStatus.selector, GearEscrow.Status.Recovered));
        vm.prank(crew); esc.submitClaim(1, 300e18, e, new bytes32[](0), bytes32(0));
        vm.expectRevert();
        vm.prank(oracle); esc.resolveClaim(cid, GearEscrow.Outcome.Accepted, bytes32(0));
    }

    function test_OwnerCannotClaimOwnNet() public {
        _buy(1); _lose(1);
        uint64 e = _publishSingle(1, DEP);
        vm.expectRevert(GearEscrow.OwnerCannotClaim.selector);
        vm.prank(fleet); esc.submitClaim(1, DEP, e, new bytes32[](0), bytes32(0));
    }

    function test_WrongPriceOrStaleEpochRejected() public {
        _buy(1); _lose(1);
        vm.prank(fund); esc.sponsor(5_000e18);
        uint64 e = _publishSingle(1, 400e18);
        vm.expectRevert(GearEscrow.BadProof.selector);
        vm.prank(crew); esc.submitClaim(1, 999e18, e, new bytes32[](0), bytes32(0));
        vm.startPrank(oracle);
        esc.publishEpoch(bytes32(uint256(1)), 0, "");
        esc.publishEpoch(bytes32(uint256(2)), 0, "");
        vm.stopPrank();
        vm.expectRevert(GearEscrow.StaleEpoch.selector);
        vm.prank(crew); esc.submitClaim(1, 400e18, e, new bytes32[](0), bytes32(0));
    }

    function test_CannotAdvertiseMoreThanPool() public {
        _buy(1); _lose(1);
        vm.expectRevert(GearEscrow.OverPromised.selector);
        vm.prank(oracle); esc.publishEpoch(bytes32(0), DEP + 1, "");
    }

    function test_RejectReleasesBountyAndNetStaysLost() public {
        _buy(1); _lose(1);
        vm.prank(fund); esc.sponsor(1_000e18);
        uint64 e = _publishSingle(1, 600e18);
        vm.prank(crew); uint256 cid = esc.submitClaim(1, 600e18, e, new bytes32[](0), bytes32(0));
        vm.prank(oracle); esc.resolveClaim(cid, GearEscrow.Outcome.Rejected, keccak256("r"));
        assertEq(uint8(_status(1)), uint8(GearEscrow.Status.Lost));
        assertEq(esc.poolAvailable(), 1_000e18 + DEP);
        _assertBooks();
    }

    function test_FlagHoldsThenExpires() public {
        _buy(1); _lose(1);
        vm.prank(fund); esc.sponsor(1_000e18);
        uint64 e = _publishSingle(1, 500e18);
        vm.prank(crew); uint256 cid = esc.submitClaim(1, 500e18, e, new bytes32[](0), bytes32(0));
        vm.prank(oracle); esc.resolveClaim(cid, GearEscrow.Outcome.Flagged, keccak256("f"));
        assertEq(esc.poolReserved(), 500e18, "still reserved while flagged");
        vm.expectRevert(GearEscrow.TooEarly.selector);
        esc.expireClaim(cid);
        vm.warp(block.timestamp + 3 days);
        esc.expireClaim(cid);
        assertEq(esc.poolReserved(), 0);
        assertEq(uint8(_status(1)), uint8(GearEscrow.Status.Lost));
        _assertBooks();
    }

    function test_UnreportedRecoveryPaysOnlyTheDeposit() public {
        _buy(1);
        vm.prank(fund); esc.sponsor(5_000e18);
        vm.prank(crew); uint256 cid = esc.submitClaim(1, 9_999e18, 0, new bytes32[](0), bytes32(0));
        (,, uint128 bounty,,, bool fromDeposit,,,) = esc.claims(cid);
        assertEq(bounty, DEP); assertTrue(fromDeposit);
        vm.prank(oracle); esc.resolveClaim(cid, GearEscrow.Outcome.Accepted, bytes32(0));
        (,,, bool unreported,,) = esc.nets(1);
        assertTrue(unreported, "penalty record");
        assertEq(usd.balanceOf(crew), DEP);
        assertEq(esc.poolAvailable(), 5_000e18, "sponsor money untouched");
        _assertBooks();
    }

    function test_RejectedUnreportedClaimRestoresDeposit() public {
        _buy(1);
        vm.prank(crew); uint256 cid = esc.submitClaim(1, 0, 0, new bytes32[](0), bytes32(0));
        vm.prank(oracle); esc.resolveClaim(cid, GearEscrow.Outcome.Rejected, bytes32(0));
        assertEq(uint8(_status(1)), uint8(GearEscrow.Status.Active));
        assertEq(esc.depositsHeld(), DEP);
        _assertBooks();
    }

    function test_ReturnRefundsDeposit() public {
        _buy(1);
        uint256 before = usd.balanceOf(fleet);
        vm.prank(supplier); esc.confirmReturn(1);
        assertEq(usd.balanceOf(fleet), before + DEP);
        assertEq(uint8(_status(1)), uint8(GearEscrow.Status.Returned));
        _assertBooks();
    }

    function test_PassportFrozenUnlessActive() public {
        _buy(2);
        vm.prank(fleet); esc.transferFrom(fleet, crew, 2);   // active: allowed
        _lose(1);
        vm.expectRevert(abi.encodeWithSelector(GearEscrow.BadStatus.selector, GearEscrow.Status.Lost));
        vm.prank(fleet); esc.transferFrom(fleet, crew, 1);
    }

    function test_OnlyRolesCanPriceAndVerify() public {
        vm.expectRevert();
        vm.prank(crew); esc.publishEpoch(bytes32(0), 0, "");
        vm.expectRevert();
        vm.prank(crew); esc.resolveClaim(1, GearEscrow.Outcome.Accepted, bytes32(0));
    }

    /// Price list built by engine/merkle.py must verify on-chain, leaf for leaf.
    function test_PythonMerkleFixtureVerifies() public {
        string memory js = vm.readFile("test/fixtures/merkle.json");
        bytes32 root = js.readBytes32(".root");
        for (uint256 i = 0; i < 11; i++) {
            string memory p = string.concat(".items[", vm.toString(i), "]");
            uint256 id = js.readUint(string.concat(p, ".netId"));
            uint64 e = uint64(js.readUint(string.concat(p, ".epoch")));
            uint128 b = uint128(vm.parseUint(js.readString(string.concat(p, ".bounty"))));
            bytes32[] memory proof = js.readBytes32Array(string.concat(p, ".proof"));
            assertTrue(_verify(proof, root, esc.leafOf(id, e, b)), "python proof must verify");
        }
    }

    function _verify(bytes32[] memory proof, bytes32 root, bytes32 leaf) internal pure returns (bool) {
        bytes32 h = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            h = h < proof[i] ? keccak256(abi.encode(h, proof[i])) : keccak256(abi.encode(proof[i], h));
        }
        return h == root;
    }
}
