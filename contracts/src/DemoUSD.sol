// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @notice Play money for the demo. Has no value; only the deployer can mint.
contract DemoUSD is ERC20, Ownable {
    constructor(address owner_) ERC20("Demo USD (play money)", "dUSD") Ownable(owner_) {}

    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }
}
