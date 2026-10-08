// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title CarbonCreditRegistry
 * @dev Minimal, robust Ethereum smart contract for registering, transferring,
 *      and retiring verified carbon credit certificates.
 */
contract CarbonCreditRegistry {
    address public admin;

    struct CreditRecord {
        string creditId;
        uint256 plantationId;
        uint256 carbonQuantity; // in integer tCO2e
        string reportHash;     // SHA-256 digest of multi-modal verification audit
        address owner;
        uint256 issuedAt;
        bool isRetired;
        uint256 retiredAt;
    }

    mapping(string => CreditRecord) private credits;
    mapping(string => bool) private exists;
    string[] public allCreditIds;

    event CreditIssued(
        string indexed creditId,
        uint256 plantationId,
        uint256 carbonQuantity,
        string reportHash,
        address indexed owner
    );

    event CreditTransferred(
        string indexed creditId,
        address indexed previousOwner,
        address indexed newOwner,
        uint256 timestamp
    );

    event CreditRetired(
        string indexed creditId,
        address indexed retiredBy,
        uint256 timestamp
    );

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only registry administrator can execute this");
        _;
    }

    constructor() {
        admin = msg.sender;
    }

    /**
     * @notice Issues and immutably records a verified carbon credit on-chain.
     */
    function issueCredit(
        string memory _creditId,
        uint256 _plantationId,
        uint256 _carbonQuantity,
        string memory _reportHash,
        address _owner
    ) public onlyAdmin returns (bool) {
        require(!exists[_creditId], "Credit ID already registered on blockchain");
        require(_carbonQuantity > 0, "Carbon quantity must be greater than zero");
        require(_owner != address(0), "Invalid owner address");

        credits[_creditId] = CreditRecord({
            creditId: _creditId,
            plantationId: _plantationId,
            carbonQuantity: _carbonQuantity,
            reportHash: _reportHash,
            owner: _owner,
            issuedAt: block.timestamp,
            isRetired: false,
            retiredAt: 0
        });

        exists[_creditId] = true;
        allCreditIds.push(_creditId);

        emit CreditIssued(_creditId, _plantationId, _carbonQuantity, _reportHash, _owner);
        return true;
    }

    /**
     * @notice Transfers ownership of a credit upon market purchase.
     */
    function transferCredit(string memory _creditId, address _newOwner) public returns (bool) {
        require(exists[_creditId], "Credit does not exist");
        CreditRecord storage record = credits[_creditId];
        require(!record.isRetired, "Cannot transfer a retired carbon credit");
        require(msg.sender == record.owner || msg.sender == admin, "Not authorized to transfer credit");
        require(_newOwner != address(0), "Invalid new owner");

        address prevOwner = record.owner;
        record.owner = _newOwner;

        emit CreditTransferred(_creditId, prevOwner, _newOwner, block.timestamp);
        return true;
    }

    /**
     * @notice Retires a credit to prevent double-spending or resale.
     */
    function retireCredit(string memory _creditId) public returns (bool) {
        require(exists[_creditId], "Credit does not exist");
        CreditRecord storage record = credits[_creditId];
        require(!record.isRetired, "Credit is already retired");
        require(msg.sender == record.owner || msg.sender == admin, "Not authorized to retire credit");

        record.isRetired = true;
        record.retiredAt = block.timestamp;

        emit CreditRetired(_creditId, record.owner, block.timestamp);
        return true;
    }

    /**
     * @notice Retrieves the full on-chain credit record.
     */
    function getCredit(string memory _creditId) public view returns (
        string memory creditId,
        uint256 plantationId,
        uint256 carbonQuantity,
        string memory reportHash,
        address owner,
        uint256 issuedAt,
        bool isRetired,
        uint256 retiredAt
    ) {
        require(exists[_creditId], "Credit does not exist");
        CreditRecord memory r = credits[_creditId];
        return (
            r.creditId,
            r.plantationId,
            r.carbonQuantity,
            r.reportHash,
            r.owner,
            r.issuedAt,
            r.isRetired,
            r.retiredAt
        );
    }

    function creditExists(string memory _creditId) public view returns (bool) {
        return exists[_creditId];
    }

    function getTotalCredits() public view returns (uint256) {
        return allCreditIds.length;
    }
}
