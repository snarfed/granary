from . import message_pb2  as _message_pb2
from . import username_proof_pb2  as _username_proof_pb2
from . import onchain_event_pb2  as _onchain_event_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class VoteType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PREVOTE: _ClassVar[VoteType]
    PRECOMMIT: _ClassVar[VoteType]

class BlockEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BLOCK_EVENT_TYPE_HEARTBEAT: _ClassVar[BlockEventType]
    BLOCK_EVENT_TYPE_MERGE_MESSAGE: _ClassVar[BlockEventType]
PREVOTE: VoteType
PRECOMMIT: VoteType
BLOCK_EVENT_TYPE_HEARTBEAT: BlockEventType
BLOCK_EVENT_TYPE_MERGE_MESSAGE: BlockEventType

class Validator(_message.Message):
    __slots__ = ("fid", "signer", "rpc_address", "shard_index", "current_height")
    FID_FIELD_NUMBER: _ClassVar[int]
    SIGNER_FIELD_NUMBER: _ClassVar[int]
    RPC_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    SHARD_INDEX_FIELD_NUMBER: _ClassVar[int]
    CURRENT_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    fid: int
    signer: bytes
    rpc_address: str
    shard_index: int
    current_height: int
    def __init__(self, fid: _Optional[int] = ..., signer: _Optional[bytes] = ..., rpc_address: _Optional[str] = ..., shard_index: _Optional[int] = ..., current_height: _Optional[int] = ...) -> None: ...

class ValidatorSet(_message.Message):
    __slots__ = ("validators",)
    VALIDATORS_FIELD_NUMBER: _ClassVar[int]
    validators: _containers.RepeatedCompositeFieldContainer[Validator]
    def __init__(self, validators: _Optional[_Iterable[_Union[Validator, _Mapping]]] = ...) -> None: ...

class Height(_message.Message):
    __slots__ = ("shard_index", "block_number")
    SHARD_INDEX_FIELD_NUMBER: _ClassVar[int]
    BLOCK_NUMBER_FIELD_NUMBER: _ClassVar[int]
    shard_index: int
    block_number: int
    def __init__(self, shard_index: _Optional[int] = ..., block_number: _Optional[int] = ...) -> None: ...

class ShardHash(_message.Message):
    __slots__ = ("shard_index", "hash")
    SHARD_INDEX_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    shard_index: int
    hash: bytes
    def __init__(self, shard_index: _Optional[int] = ..., hash: _Optional[bytes] = ...) -> None: ...

class Vote(_message.Message):
    __slots__ = ("type", "height", "round", "value", "voter")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    ROUND_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    VOTER_FIELD_NUMBER: _ClassVar[int]
    type: VoteType
    height: Height
    round: int
    value: ShardHash
    voter: bytes
    def __init__(self, type: _Optional[_Union[VoteType, str]] = ..., height: _Optional[_Union[Height, _Mapping]] = ..., round: _Optional[int] = ..., value: _Optional[_Union[ShardHash, _Mapping]] = ..., voter: _Optional[bytes] = ...) -> None: ...

class CommitSignature(_message.Message):
    __slots__ = ("signer", "signature")
    SIGNER_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    signer: bytes
    signature: bytes
    def __init__(self, signer: _Optional[bytes] = ..., signature: _Optional[bytes] = ...) -> None: ...

class Commits(_message.Message):
    __slots__ = ("height", "round", "value", "signatures")
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    ROUND_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    SIGNATURES_FIELD_NUMBER: _ClassVar[int]
    height: Height
    round: int
    value: ShardHash
    signatures: _containers.RepeatedCompositeFieldContainer[CommitSignature]
    def __init__(self, height: _Optional[_Union[Height, _Mapping]] = ..., round: _Optional[int] = ..., value: _Optional[_Union[ShardHash, _Mapping]] = ..., signatures: _Optional[_Iterable[_Union[CommitSignature, _Mapping]]] = ...) -> None: ...

class Proposal(_message.Message):
    __slots__ = ("height", "round", "pol_round", "proposer", "value")
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    ROUND_FIELD_NUMBER: _ClassVar[int]
    POL_ROUND_FIELD_NUMBER: _ClassVar[int]
    PROPOSER_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    height: Height
    round: int
    pol_round: int
    proposer: bytes
    value: ShardHash
    def __init__(self, height: _Optional[_Union[Height, _Mapping]] = ..., round: _Optional[int] = ..., pol_round: _Optional[int] = ..., proposer: _Optional[bytes] = ..., value: _Optional[_Union[ShardHash, _Mapping]] = ...) -> None: ...

class FullProposal(_message.Message):
    __slots__ = ("height", "round", "proposer", "block", "shard")
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    ROUND_FIELD_NUMBER: _ClassVar[int]
    PROPOSER_FIELD_NUMBER: _ClassVar[int]
    BLOCK_FIELD_NUMBER: _ClassVar[int]
    SHARD_FIELD_NUMBER: _ClassVar[int]
    height: Height
    round: int
    proposer: bytes
    block: Block
    shard: ShardChunk
    def __init__(self, height: _Optional[_Union[Height, _Mapping]] = ..., round: _Optional[int] = ..., proposer: _Optional[bytes] = ..., block: _Optional[_Union[Block, _Mapping]] = ..., shard: _Optional[_Union[ShardChunk, _Mapping]] = ...) -> None: ...

class DecidedValue(_message.Message):
    __slots__ = ("block", "shard")
    BLOCK_FIELD_NUMBER: _ClassVar[int]
    SHARD_FIELD_NUMBER: _ClassVar[int]
    block: Block
    shard: ShardChunk
    def __init__(self, block: _Optional[_Union[Block, _Mapping]] = ..., shard: _Optional[_Union[ShardChunk, _Mapping]] = ...) -> None: ...

class ReadNodeMessage(_message.Message):
    __slots__ = ("decided_value",)
    DECIDED_VALUE_FIELD_NUMBER: _ClassVar[int]
    decided_value: DecidedValue
    def __init__(self, decided_value: _Optional[_Union[DecidedValue, _Mapping]] = ...) -> None: ...

class ConsensusMessage(_message.Message):
    __slots__ = ("vote", "proposal", "signature")
    VOTE_FIELD_NUMBER: _ClassVar[int]
    PROPOSAL_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    vote: Vote
    proposal: Proposal
    signature: bytes
    def __init__(self, vote: _Optional[_Union[Vote, _Mapping]] = ..., proposal: _Optional[_Union[Proposal, _Mapping]] = ..., signature: _Optional[bytes] = ...) -> None: ...

class HeartbeatEventBody(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class MergeMessageEventBody(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: _message_pb2.Message
    def __init__(self, message: _Optional[_Union[_message_pb2.Message, _Mapping]] = ...) -> None: ...

class BlockEventData(_message.Message):
    __slots__ = ("seqnum", "type", "block_number", "event_index", "block_timestamp", "heartbeat_event_body", "merge_message_event_body")
    SEQNUM_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    BLOCK_NUMBER_FIELD_NUMBER: _ClassVar[int]
    EVENT_INDEX_FIELD_NUMBER: _ClassVar[int]
    BLOCK_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_EVENT_BODY_FIELD_NUMBER: _ClassVar[int]
    MERGE_MESSAGE_EVENT_BODY_FIELD_NUMBER: _ClassVar[int]
    seqnum: int
    type: BlockEventType
    block_number: int
    event_index: int
    block_timestamp: int
    heartbeat_event_body: HeartbeatEventBody
    merge_message_event_body: MergeMessageEventBody
    def __init__(self, seqnum: _Optional[int] = ..., type: _Optional[_Union[BlockEventType, str]] = ..., block_number: _Optional[int] = ..., event_index: _Optional[int] = ..., block_timestamp: _Optional[int] = ..., heartbeat_event_body: _Optional[_Union[HeartbeatEventBody, _Mapping]] = ..., merge_message_event_body: _Optional[_Union[MergeMessageEventBody, _Mapping]] = ...) -> None: ...

class BlockEvent(_message.Message):
    __slots__ = ("hash", "data")
    HASH_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    hash: bytes
    data: BlockEventData
    def __init__(self, hash: _Optional[bytes] = ..., data: _Optional[_Union[BlockEventData, _Mapping]] = ...) -> None: ...

class BlockHeader(_message.Message):
    __slots__ = ("height", "timestamp", "version", "chain_id", "shard_witnesses_hash", "parent_hash", "state_root", "events_hash")
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    SHARD_WITNESSES_HASH_FIELD_NUMBER: _ClassVar[int]
    PARENT_HASH_FIELD_NUMBER: _ClassVar[int]
    STATE_ROOT_FIELD_NUMBER: _ClassVar[int]
    EVENTS_HASH_FIELD_NUMBER: _ClassVar[int]
    height: Height
    timestamp: int
    version: int
    chain_id: _message_pb2.FarcasterNetwork
    shard_witnesses_hash: bytes
    parent_hash: bytes
    state_root: bytes
    events_hash: bytes
    def __init__(self, height: _Optional[_Union[Height, _Mapping]] = ..., timestamp: _Optional[int] = ..., version: _Optional[int] = ..., chain_id: _Optional[_Union[_message_pb2.FarcasterNetwork, str]] = ..., shard_witnesses_hash: _Optional[bytes] = ..., parent_hash: _Optional[bytes] = ..., state_root: _Optional[bytes] = ..., events_hash: _Optional[bytes] = ...) -> None: ...

class ShardWitness(_message.Message):
    __slots__ = ("shard_chunk_witnesses",)
    SHARD_CHUNK_WITNESSES_FIELD_NUMBER: _ClassVar[int]
    shard_chunk_witnesses: _containers.RepeatedCompositeFieldContainer[ShardChunkWitness]
    def __init__(self, shard_chunk_witnesses: _Optional[_Iterable[_Union[ShardChunkWitness, _Mapping]]] = ...) -> None: ...

class ShardChunkWitness(_message.Message):
    __slots__ = ("height", "shard_root", "shard_hash")
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    SHARD_ROOT_FIELD_NUMBER: _ClassVar[int]
    SHARD_HASH_FIELD_NUMBER: _ClassVar[int]
    height: Height
    shard_root: bytes
    shard_hash: bytes
    def __init__(self, height: _Optional[_Union[Height, _Mapping]] = ..., shard_root: _Optional[bytes] = ..., shard_hash: _Optional[bytes] = ...) -> None: ...

class Block(_message.Message):
    __slots__ = ("header", "hash", "shard_witness", "commits", "transactions", "events")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    SHARD_WITNESS_FIELD_NUMBER: _ClassVar[int]
    COMMITS_FIELD_NUMBER: _ClassVar[int]
    TRANSACTIONS_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    header: BlockHeader
    hash: bytes
    shard_witness: ShardWitness
    commits: Commits
    transactions: _containers.RepeatedCompositeFieldContainer[Transaction]
    events: _containers.RepeatedCompositeFieldContainer[BlockEvent]
    def __init__(self, header: _Optional[_Union[BlockHeader, _Mapping]] = ..., hash: _Optional[bytes] = ..., shard_witness: _Optional[_Union[ShardWitness, _Mapping]] = ..., commits: _Optional[_Union[Commits, _Mapping]] = ..., transactions: _Optional[_Iterable[_Union[Transaction, _Mapping]]] = ..., events: _Optional[_Iterable[_Union[BlockEvent, _Mapping]]] = ...) -> None: ...

class ShardHeader(_message.Message):
    __slots__ = ("height", "timestamp", "parent_hash", "shard_root")
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    PARENT_HASH_FIELD_NUMBER: _ClassVar[int]
    SHARD_ROOT_FIELD_NUMBER: _ClassVar[int]
    height: Height
    timestamp: int
    parent_hash: bytes
    shard_root: bytes
    def __init__(self, height: _Optional[_Union[Height, _Mapping]] = ..., timestamp: _Optional[int] = ..., parent_hash: _Optional[bytes] = ..., shard_root: _Optional[bytes] = ...) -> None: ...

class ShardChunk(_message.Message):
    __slots__ = ("header", "hash", "transactions", "commits")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    TRANSACTIONS_FIELD_NUMBER: _ClassVar[int]
    COMMITS_FIELD_NUMBER: _ClassVar[int]
    header: ShardHeader
    hash: bytes
    transactions: _containers.RepeatedCompositeFieldContainer[Transaction]
    commits: Commits
    def __init__(self, header: _Optional[_Union[ShardHeader, _Mapping]] = ..., hash: _Optional[bytes] = ..., transactions: _Optional[_Iterable[_Union[Transaction, _Mapping]]] = ..., commits: _Optional[_Union[Commits, _Mapping]] = ...) -> None: ...

class Transaction(_message.Message):
    __slots__ = ("fid", "user_messages", "system_messages", "account_root")
    FID_FIELD_NUMBER: _ClassVar[int]
    USER_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ROOT_FIELD_NUMBER: _ClassVar[int]
    fid: int
    user_messages: _containers.RepeatedCompositeFieldContainer[_message_pb2.Message]
    system_messages: _containers.RepeatedCompositeFieldContainer[ValidatorMessage]
    account_root: bytes
    def __init__(self, fid: _Optional[int] = ..., user_messages: _Optional[_Iterable[_Union[_message_pb2.Message, _Mapping]]] = ..., system_messages: _Optional[_Iterable[_Union[ValidatorMessage, _Mapping]]] = ..., account_root: _Optional[bytes] = ...) -> None: ...

class FnameTransfer(_message.Message):
    __slots__ = ("id", "from_fid", "proof")
    ID_FIELD_NUMBER: _ClassVar[int]
    FROM_FID_FIELD_NUMBER: _ClassVar[int]
    PROOF_FIELD_NUMBER: _ClassVar[int]
    id: int
    from_fid: int
    proof: _username_proof_pb2.UserNameProof
    def __init__(self, id: _Optional[int] = ..., from_fid: _Optional[int] = ..., proof: _Optional[_Union[_username_proof_pb2.UserNameProof, _Mapping]] = ...) -> None: ...

class ValidatorMessage(_message.Message):
    __slots__ = ("on_chain_event", "fname_transfer", "block_event")
    ON_CHAIN_EVENT_FIELD_NUMBER: _ClassVar[int]
    FNAME_TRANSFER_FIELD_NUMBER: _ClassVar[int]
    BLOCK_EVENT_FIELD_NUMBER: _ClassVar[int]
    on_chain_event: _onchain_event_pb2.OnChainEvent
    fname_transfer: FnameTransfer
    block_event: BlockEvent
    def __init__(self, on_chain_event: _Optional[_Union[_onchain_event_pb2.OnChainEvent, _Mapping]] = ..., fname_transfer: _Optional[_Union[FnameTransfer, _Mapping]] = ..., block_event: _Optional[_Union[BlockEvent, _Mapping]] = ...) -> None: ...

class MempoolMessage(_message.Message):
    __slots__ = ("user_message",)
    USER_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    user_message: _message_pb2.Message
    def __init__(self, user_message: _Optional[_Union[_message_pb2.Message, _Mapping]] = ...) -> None: ...

class StatusMessage(_message.Message):
    __slots__ = ("peer_id", "height", "min_height")
    PEER_ID_FIELD_NUMBER: _ClassVar[int]
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    MIN_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    peer_id: bytes
    height: Height
    min_height: Height
    def __init__(self, peer_id: _Optional[bytes] = ..., height: _Optional[_Union[Height, _Mapping]] = ..., min_height: _Optional[_Union[Height, _Mapping]] = ...) -> None: ...

class SyncValueRequest(_message.Message):
    __slots__ = ("height",)
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    height: Height
    def __init__(self, height: _Optional[_Union[Height, _Mapping]] = ...) -> None: ...

class SyncVoteSetRequest(_message.Message):
    __slots__ = ("height", "round")
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    ROUND_FIELD_NUMBER: _ClassVar[int]
    height: Height
    round: int
    def __init__(self, height: _Optional[_Union[Height, _Mapping]] = ..., round: _Optional[int] = ...) -> None: ...

class SyncRequest(_message.Message):
    __slots__ = ("value", "vote_set")
    VALUE_FIELD_NUMBER: _ClassVar[int]
    VOTE_SET_FIELD_NUMBER: _ClassVar[int]
    value: SyncValueRequest
    vote_set: SyncVoteSetRequest
    def __init__(self, value: _Optional[_Union[SyncValueRequest, _Mapping]] = ..., vote_set: _Optional[_Union[SyncVoteSetRequest, _Mapping]] = ...) -> None: ...

class SyncValueResponse(_message.Message):
    __slots__ = ("height", "full_value", "commits")
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    FULL_VALUE_FIELD_NUMBER: _ClassVar[int]
    COMMITS_FIELD_NUMBER: _ClassVar[int]
    height: Height
    full_value: bytes
    commits: Commits
    def __init__(self, height: _Optional[_Union[Height, _Mapping]] = ..., full_value: _Optional[bytes] = ..., commits: _Optional[_Union[Commits, _Mapping]] = ...) -> None: ...

class SyncVoteSetResponse(_message.Message):
    __slots__ = ("height", "round", "votes", "signatures")
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    ROUND_FIELD_NUMBER: _ClassVar[int]
    VOTES_FIELD_NUMBER: _ClassVar[int]
    SIGNATURES_FIELD_NUMBER: _ClassVar[int]
    height: Height
    round: int
    votes: _containers.RepeatedCompositeFieldContainer[Vote]
    signatures: _containers.RepeatedScalarFieldContainer[bytes]
    def __init__(self, height: _Optional[_Union[Height, _Mapping]] = ..., round: _Optional[int] = ..., votes: _Optional[_Iterable[_Union[Vote, _Mapping]]] = ..., signatures: _Optional[_Iterable[bytes]] = ...) -> None: ...

class SyncResponse(_message.Message):
    __slots__ = ("value", "vote_set")
    VALUE_FIELD_NUMBER: _ClassVar[int]
    VOTE_SET_FIELD_NUMBER: _ClassVar[int]
    value: SyncValueResponse
    vote_set: SyncVoteSetResponse
    def __init__(self, value: _Optional[_Union[SyncValueResponse, _Mapping]] = ..., vote_set: _Optional[_Union[SyncVoteSetResponse, _Mapping]] = ...) -> None: ...
