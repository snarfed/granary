from . import message_pb2  as _message_pb2
from . import blocks_pb2  as _blocks_pb2
from . import hub_event_pb2  as _hub_event_pb2
from . import username_proof_pb2  as _username_proof_pb2
from . import onchain_event_pb2  as _onchain_event_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StoreType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STORE_TYPE_NONE: _ClassVar[StoreType]
    STORE_TYPE_CASTS: _ClassVar[StoreType]
    STORE_TYPE_LINKS: _ClassVar[StoreType]
    STORE_TYPE_REACTIONS: _ClassVar[StoreType]
    STORE_TYPE_USER_DATA: _ClassVar[StoreType]
    STORE_TYPE_VERIFICATIONS: _ClassVar[StoreType]
    STORE_TYPE_USERNAME_PROOFS: _ClassVar[StoreType]
    STORE_TYPE_STORAGE_LENDS: _ClassVar[StoreType]
STORE_TYPE_NONE: StoreType
STORE_TYPE_CASTS: StoreType
STORE_TYPE_LINKS: StoreType
STORE_TYPE_REACTIONS: StoreType
STORE_TYPE_USER_DATA: StoreType
STORE_TYPE_VERIFICATIONS: StoreType
STORE_TYPE_USERNAME_PROOFS: StoreType
STORE_TYPE_STORAGE_LENDS: StoreType

class BlocksRequest(_message.Message):
    __slots__ = ("shard_id", "start_block_number", "stop_block_number")
    SHARD_ID_FIELD_NUMBER: _ClassVar[int]
    START_BLOCK_NUMBER_FIELD_NUMBER: _ClassVar[int]
    STOP_BLOCK_NUMBER_FIELD_NUMBER: _ClassVar[int]
    shard_id: int
    start_block_number: int
    stop_block_number: int
    def __init__(self, shard_id: _Optional[int] = ..., start_block_number: _Optional[int] = ..., stop_block_number: _Optional[int] = ...) -> None: ...

class ShardChunksRequest(_message.Message):
    __slots__ = ("shard_id", "start_block_number", "stop_block_number")
    SHARD_ID_FIELD_NUMBER: _ClassVar[int]
    START_BLOCK_NUMBER_FIELD_NUMBER: _ClassVar[int]
    STOP_BLOCK_NUMBER_FIELD_NUMBER: _ClassVar[int]
    shard_id: int
    start_block_number: int
    stop_block_number: int
    def __init__(self, shard_id: _Optional[int] = ..., start_block_number: _Optional[int] = ..., stop_block_number: _Optional[int] = ...) -> None: ...

class ShardChunksResponse(_message.Message):
    __slots__ = ("shard_chunks",)
    SHARD_CHUNKS_FIELD_NUMBER: _ClassVar[int]
    shard_chunks: _containers.RepeatedCompositeFieldContainer[_blocks_pb2.ShardChunk]
    def __init__(self, shard_chunks: _Optional[_Iterable[_Union[_blocks_pb2.ShardChunk, _Mapping]]] = ...) -> None: ...

class SubscribeRequest(_message.Message):
    __slots__ = ("event_types", "from_id", "shard_index")
    EVENT_TYPES_FIELD_NUMBER: _ClassVar[int]
    FROM_ID_FIELD_NUMBER: _ClassVar[int]
    SHARD_INDEX_FIELD_NUMBER: _ClassVar[int]
    event_types: _containers.RepeatedScalarFieldContainer[_hub_event_pb2.HubEventType]
    from_id: int
    shard_index: int
    def __init__(self, event_types: _Optional[_Iterable[_Union[_hub_event_pb2.HubEventType, str]]] = ..., from_id: _Optional[int] = ..., shard_index: _Optional[int] = ...) -> None: ...

class DbStats(_message.Message):
    __slots__ = ("num_messages", "num_fid_registrations", "approx_size")
    NUM_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    NUM_FID_REGISTRATIONS_FIELD_NUMBER: _ClassVar[int]
    APPROX_SIZE_FIELD_NUMBER: _ClassVar[int]
    num_messages: int
    num_fid_registrations: int
    approx_size: int
    def __init__(self, num_messages: _Optional[int] = ..., num_fid_registrations: _Optional[int] = ..., approx_size: _Optional[int] = ...) -> None: ...

class ShardInfo(_message.Message):
    __slots__ = ("shard_id", "max_height", "num_messages", "num_fid_registrations", "approx_size", "block_delay", "mempool_size", "num_onchain_events")
    SHARD_ID_FIELD_NUMBER: _ClassVar[int]
    MAX_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    NUM_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    NUM_FID_REGISTRATIONS_FIELD_NUMBER: _ClassVar[int]
    APPROX_SIZE_FIELD_NUMBER: _ClassVar[int]
    BLOCK_DELAY_FIELD_NUMBER: _ClassVar[int]
    MEMPOOL_SIZE_FIELD_NUMBER: _ClassVar[int]
    NUM_ONCHAIN_EVENTS_FIELD_NUMBER: _ClassVar[int]
    shard_id: int
    max_height: int
    num_messages: int
    num_fid_registrations: int
    approx_size: int
    block_delay: int
    mempool_size: int
    num_onchain_events: int
    def __init__(self, shard_id: _Optional[int] = ..., max_height: _Optional[int] = ..., num_messages: _Optional[int] = ..., num_fid_registrations: _Optional[int] = ..., approx_size: _Optional[int] = ..., block_delay: _Optional[int] = ..., mempool_size: _Optional[int] = ..., num_onchain_events: _Optional[int] = ...) -> None: ...

class GetInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetInfoResponse(_message.Message):
    __slots__ = ("version", "db_stats", "peerId", "num_shards", "shard_infos", "next_engine_version_timestamp")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    DB_STATS_FIELD_NUMBER: _ClassVar[int]
    PEERID_FIELD_NUMBER: _ClassVar[int]
    NUM_SHARDS_FIELD_NUMBER: _ClassVar[int]
    SHARD_INFOS_FIELD_NUMBER: _ClassVar[int]
    NEXT_ENGINE_VERSION_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    version: str
    db_stats: DbStats
    peerId: str
    num_shards: int
    shard_infos: _containers.RepeatedCompositeFieldContainer[ShardInfo]
    next_engine_version_timestamp: int
    def __init__(self, version: _Optional[str] = ..., db_stats: _Optional[_Union[DbStats, _Mapping]] = ..., peerId: _Optional[str] = ..., num_shards: _Optional[int] = ..., shard_infos: _Optional[_Iterable[_Union[ShardInfo, _Mapping]]] = ..., next_engine_version_timestamp: _Optional[int] = ...) -> None: ...

class EventRequest(_message.Message):
    __slots__ = ("id", "shard_index")
    ID_FIELD_NUMBER: _ClassVar[int]
    SHARD_INDEX_FIELD_NUMBER: _ClassVar[int]
    id: int
    shard_index: int
    def __init__(self, id: _Optional[int] = ..., shard_index: _Optional[int] = ...) -> None: ...

class FidRequest(_message.Message):
    __slots__ = ("fid", "page_size", "page_token", "reverse")
    FID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    fid: int
    page_size: int
    page_token: bytes
    reverse: bool
    def __init__(self, fid: _Optional[int] = ..., page_size: _Optional[int] = ..., page_token: _Optional[bytes] = ..., reverse: bool = ...) -> None: ...

class FidTimestampRequest(_message.Message):
    __slots__ = ("fid", "page_size", "page_token", "reverse", "start_timestamp", "stop_timestamp")
    FID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    START_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    STOP_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    fid: int
    page_size: int
    page_token: bytes
    reverse: bool
    start_timestamp: int
    stop_timestamp: int
    def __init__(self, fid: _Optional[int] = ..., page_size: _Optional[int] = ..., page_token: _Optional[bytes] = ..., reverse: bool = ..., start_timestamp: _Optional[int] = ..., stop_timestamp: _Optional[int] = ...) -> None: ...

class FidsRequest(_message.Message):
    __slots__ = ("page_size", "page_token", "reverse", "shard_id")
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    SHARD_ID_FIELD_NUMBER: _ClassVar[int]
    page_size: int
    page_token: bytes
    reverse: bool
    shard_id: int
    def __init__(self, page_size: _Optional[int] = ..., page_token: _Optional[bytes] = ..., reverse: bool = ..., shard_id: _Optional[int] = ...) -> None: ...

class FidsResponse(_message.Message):
    __slots__ = ("fids", "next_page_token")
    FIDS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    fids: _containers.RepeatedScalarFieldContainer[int]
    next_page_token: bytes
    def __init__(self, fids: _Optional[_Iterable[int]] = ..., next_page_token: _Optional[bytes] = ...) -> None: ...

class MessagesResponse(_message.Message):
    __slots__ = ("messages", "next_page_token")
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[_message_pb2.Message]
    next_page_token: bytes
    def __init__(self, messages: _Optional[_Iterable[_Union[_message_pb2.Message, _Mapping]]] = ..., next_page_token: _Optional[bytes] = ...) -> None: ...

class CastsByParentRequest(_message.Message):
    __slots__ = ("parent_cast_id", "parent_url", "page_size", "page_token", "reverse")
    PARENT_CAST_ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_URL_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    parent_cast_id: _message_pb2.CastId
    parent_url: str
    page_size: int
    page_token: bytes
    reverse: bool
    def __init__(self, parent_cast_id: _Optional[_Union[_message_pb2.CastId, _Mapping]] = ..., parent_url: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[bytes] = ..., reverse: bool = ...) -> None: ...

class ReactionRequest(_message.Message):
    __slots__ = ("fid", "reaction_type", "target_cast_id", "target_url")
    FID_FIELD_NUMBER: _ClassVar[int]
    REACTION_TYPE_FIELD_NUMBER: _ClassVar[int]
    TARGET_CAST_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_URL_FIELD_NUMBER: _ClassVar[int]
    fid: int
    reaction_type: _message_pb2.ReactionType
    target_cast_id: _message_pb2.CastId
    target_url: str
    def __init__(self, fid: _Optional[int] = ..., reaction_type: _Optional[_Union[_message_pb2.ReactionType, str]] = ..., target_cast_id: _Optional[_Union[_message_pb2.CastId, _Mapping]] = ..., target_url: _Optional[str] = ...) -> None: ...

class ReactionsByFidRequest(_message.Message):
    __slots__ = ("fid", "reaction_type", "page_size", "page_token", "reverse")
    FID_FIELD_NUMBER: _ClassVar[int]
    REACTION_TYPE_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    fid: int
    reaction_type: _message_pb2.ReactionType
    page_size: int
    page_token: bytes
    reverse: bool
    def __init__(self, fid: _Optional[int] = ..., reaction_type: _Optional[_Union[_message_pb2.ReactionType, str]] = ..., page_size: _Optional[int] = ..., page_token: _Optional[bytes] = ..., reverse: bool = ...) -> None: ...

class ReactionsByTargetRequest(_message.Message):
    __slots__ = ("target_cast_id", "target_url", "reaction_type", "page_size", "page_token", "reverse")
    TARGET_CAST_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_URL_FIELD_NUMBER: _ClassVar[int]
    REACTION_TYPE_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    target_cast_id: _message_pb2.CastId
    target_url: str
    reaction_type: _message_pb2.ReactionType
    page_size: int
    page_token: bytes
    reverse: bool
    def __init__(self, target_cast_id: _Optional[_Union[_message_pb2.CastId, _Mapping]] = ..., target_url: _Optional[str] = ..., reaction_type: _Optional[_Union[_message_pb2.ReactionType, str]] = ..., page_size: _Optional[int] = ..., page_token: _Optional[bytes] = ..., reverse: bool = ...) -> None: ...

class UserDataRequest(_message.Message):
    __slots__ = ("fid", "user_data_type")
    FID_FIELD_NUMBER: _ClassVar[int]
    USER_DATA_TYPE_FIELD_NUMBER: _ClassVar[int]
    fid: int
    user_data_type: _message_pb2.UserDataType
    def __init__(self, fid: _Optional[int] = ..., user_data_type: _Optional[_Union[_message_pb2.UserDataType, str]] = ...) -> None: ...

class OnChainEventRequest(_message.Message):
    __slots__ = ("fid", "event_type", "page_size", "page_token", "reverse")
    FID_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    fid: int
    event_type: _onchain_event_pb2.OnChainEventType
    page_size: int
    page_token: bytes
    reverse: bool
    def __init__(self, fid: _Optional[int] = ..., event_type: _Optional[_Union[_onchain_event_pb2.OnChainEventType, str]] = ..., page_size: _Optional[int] = ..., page_token: _Optional[bytes] = ..., reverse: bool = ...) -> None: ...

class OnChainEventResponse(_message.Message):
    __slots__ = ("events", "next_page_token")
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[_onchain_event_pb2.OnChainEvent]
    next_page_token: bytes
    def __init__(self, events: _Optional[_Iterable[_Union[_onchain_event_pb2.OnChainEvent, _Mapping]]] = ..., next_page_token: _Optional[bytes] = ...) -> None: ...

class TierDetails(_message.Message):
    __slots__ = ("tier_type", "expires_at")
    TIER_TYPE_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    tier_type: _onchain_event_pb2.TierType
    expires_at: int
    def __init__(self, tier_type: _Optional[_Union[_onchain_event_pb2.TierType, str]] = ..., expires_at: _Optional[int] = ...) -> None: ...

class StorageLimitsResponse(_message.Message):
    __slots__ = ("limits", "units", "unit_details", "tier_subscriptions")
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    UNIT_DETAILS_FIELD_NUMBER: _ClassVar[int]
    TIER_SUBSCRIPTIONS_FIELD_NUMBER: _ClassVar[int]
    limits: _containers.RepeatedCompositeFieldContainer[StorageLimit]
    units: int
    unit_details: _containers.RepeatedCompositeFieldContainer[StorageUnitDetails]
    tier_subscriptions: _containers.RepeatedCompositeFieldContainer[TierDetails]
    def __init__(self, limits: _Optional[_Iterable[_Union[StorageLimit, _Mapping]]] = ..., units: _Optional[int] = ..., unit_details: _Optional[_Iterable[_Union[StorageUnitDetails, _Mapping]]] = ..., tier_subscriptions: _Optional[_Iterable[_Union[TierDetails, _Mapping]]] = ...) -> None: ...

class StorageUnitDetails(_message.Message):
    __slots__ = ("unit_type", "unit_size", "purchased_unit_size", "lent_unit_size", "borrowed_unit_size")
    UNIT_TYPE_FIELD_NUMBER: _ClassVar[int]
    UNIT_SIZE_FIELD_NUMBER: _ClassVar[int]
    PURCHASED_UNIT_SIZE_FIELD_NUMBER: _ClassVar[int]
    LENT_UNIT_SIZE_FIELD_NUMBER: _ClassVar[int]
    BORROWED_UNIT_SIZE_FIELD_NUMBER: _ClassVar[int]
    unit_type: _message_pb2.StorageUnitType
    unit_size: int
    purchased_unit_size: int
    lent_unit_size: int
    borrowed_unit_size: int
    def __init__(self, unit_type: _Optional[_Union[_message_pb2.StorageUnitType, str]] = ..., unit_size: _Optional[int] = ..., purchased_unit_size: _Optional[int] = ..., lent_unit_size: _Optional[int] = ..., borrowed_unit_size: _Optional[int] = ...) -> None: ...

class StorageLimit(_message.Message):
    __slots__ = ("store_type", "name", "limit", "used", "earliestTimestamp", "earliestHash")
    STORE_TYPE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    USED_FIELD_NUMBER: _ClassVar[int]
    EARLIESTTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    EARLIESTHASH_FIELD_NUMBER: _ClassVar[int]
    store_type: StoreType
    name: str
    limit: int
    used: int
    earliestTimestamp: int
    earliestHash: bytes
    def __init__(self, store_type: _Optional[_Union[StoreType, str]] = ..., name: _Optional[str] = ..., limit: _Optional[int] = ..., used: _Optional[int] = ..., earliestTimestamp: _Optional[int] = ..., earliestHash: _Optional[bytes] = ...) -> None: ...

class UsernameProofRequest(_message.Message):
    __slots__ = ("name",)
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: bytes
    def __init__(self, name: _Optional[bytes] = ...) -> None: ...

class UsernameProofsResponse(_message.Message):
    __slots__ = ("proofs",)
    PROOFS_FIELD_NUMBER: _ClassVar[int]
    proofs: _containers.RepeatedCompositeFieldContainer[_username_proof_pb2.UserNameProof]
    def __init__(self, proofs: _Optional[_Iterable[_Union[_username_proof_pb2.UserNameProof, _Mapping]]] = ...) -> None: ...

class ValidationResponse(_message.Message):
    __slots__ = ("valid", "message")
    VALID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    valid: bool
    message: _message_pb2.Message
    def __init__(self, valid: bool = ..., message: _Optional[_Union[_message_pb2.Message, _Mapping]] = ...) -> None: ...

class VerificationRequest(_message.Message):
    __slots__ = ("fid", "address")
    FID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    fid: int
    address: bytes
    def __init__(self, fid: _Optional[int] = ..., address: _Optional[bytes] = ...) -> None: ...

class SignerRequest(_message.Message):
    __slots__ = ("fid", "signer")
    FID_FIELD_NUMBER: _ClassVar[int]
    SIGNER_FIELD_NUMBER: _ClassVar[int]
    fid: int
    signer: bytes
    def __init__(self, fid: _Optional[int] = ..., signer: _Optional[bytes] = ...) -> None: ...

class LinkRequest(_message.Message):
    __slots__ = ("fid", "link_type", "target_fid")
    FID_FIELD_NUMBER: _ClassVar[int]
    LINK_TYPE_FIELD_NUMBER: _ClassVar[int]
    TARGET_FID_FIELD_NUMBER: _ClassVar[int]
    fid: int
    link_type: str
    target_fid: int
    def __init__(self, fid: _Optional[int] = ..., link_type: _Optional[str] = ..., target_fid: _Optional[int] = ...) -> None: ...

class LinksByFidRequest(_message.Message):
    __slots__ = ("fid", "link_type", "page_size", "page_token", "reverse")
    FID_FIELD_NUMBER: _ClassVar[int]
    LINK_TYPE_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    fid: int
    link_type: str
    page_size: int
    page_token: bytes
    reverse: bool
    def __init__(self, fid: _Optional[int] = ..., link_type: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[bytes] = ..., reverse: bool = ...) -> None: ...

class LinksByTargetRequest(_message.Message):
    __slots__ = ("target_fid", "link_type", "page_size", "page_token", "reverse")
    TARGET_FID_FIELD_NUMBER: _ClassVar[int]
    LINK_TYPE_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    target_fid: int
    link_type: str
    page_size: int
    page_token: bytes
    reverse: bool
    def __init__(self, target_fid: _Optional[int] = ..., link_type: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[bytes] = ..., reverse: bool = ...) -> None: ...

class IdRegistryEventByAddressRequest(_message.Message):
    __slots__ = ("address",)
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    address: bytes
    def __init__(self, address: _Optional[bytes] = ...) -> None: ...

class SubmitBulkMessagesRequest(_message.Message):
    __slots__ = ("messages",)
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[_message_pb2.Message]
    def __init__(self, messages: _Optional[_Iterable[_Union[_message_pb2.Message, _Mapping]]] = ...) -> None: ...

class MessageError(_message.Message):
    __slots__ = ("hash", "errCode", "message")
    HASH_FIELD_NUMBER: _ClassVar[int]
    ERRCODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    hash: bytes
    errCode: str
    message: str
    def __init__(self, hash: _Optional[bytes] = ..., errCode: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class BulkMessageResponse(_message.Message):
    __slots__ = ("message", "message_error")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_ERROR_FIELD_NUMBER: _ClassVar[int]
    message: _message_pb2.Message
    message_error: MessageError
    def __init__(self, message: _Optional[_Union[_message_pb2.Message, _Mapping]] = ..., message_error: _Optional[_Union[MessageError, _Mapping]] = ...) -> None: ...

class SubmitBulkMessagesResponse(_message.Message):
    __slots__ = ("messages",)
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[BulkMessageResponse]
    def __init__(self, messages: _Optional[_Iterable[_Union[BulkMessageResponse, _Mapping]]] = ...) -> None: ...

class TrieNodeMetadataRequest(_message.Message):
    __slots__ = ("shard_id", "prefix")
    SHARD_ID_FIELD_NUMBER: _ClassVar[int]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    shard_id: int
    prefix: bytes
    def __init__(self, shard_id: _Optional[int] = ..., prefix: _Optional[bytes] = ...) -> None: ...

class TrieNodeMetadataResponse(_message.Message):
    __slots__ = ("prefix", "num_messages", "hash", "children")
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    NUM_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    CHILDREN_FIELD_NUMBER: _ClassVar[int]
    prefix: bytes
    num_messages: int
    hash: str
    children: _containers.RepeatedCompositeFieldContainer[TrieNodeMetadataResponse]
    def __init__(self, prefix: _Optional[bytes] = ..., num_messages: _Optional[int] = ..., hash: _Optional[str] = ..., children: _Optional[_Iterable[_Union[TrieNodeMetadataResponse, _Mapping]]] = ...) -> None: ...

class EventsRequest(_message.Message):
    __slots__ = ("start_id", "shard_index", "stop_id", "page_size", "page_token", "reverse")
    START_ID_FIELD_NUMBER: _ClassVar[int]
    SHARD_INDEX_FIELD_NUMBER: _ClassVar[int]
    STOP_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    start_id: int
    shard_index: int
    stop_id: int
    page_size: int
    page_token: bytes
    reverse: bool
    def __init__(self, start_id: _Optional[int] = ..., shard_index: _Optional[int] = ..., stop_id: _Optional[int] = ..., page_size: _Optional[int] = ..., page_token: _Optional[bytes] = ..., reverse: bool = ...) -> None: ...

class EventsResponse(_message.Message):
    __slots__ = ("events", "next_page_token")
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[_hub_event_pb2.HubEvent]
    next_page_token: bytes
    def __init__(self, events: _Optional[_Iterable[_Union[_hub_event_pb2.HubEvent, _Mapping]]] = ..., next_page_token: _Optional[bytes] = ...) -> None: ...

class FidAddressTypeRequest(_message.Message):
    __slots__ = ("fid", "address")
    FID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    fid: int
    address: bytes
    def __init__(self, fid: _Optional[int] = ..., address: _Optional[bytes] = ...) -> None: ...

class FidAddressTypeResponse(_message.Message):
    __slots__ = ("is_custody", "is_auth", "is_verified")
    IS_CUSTODY_FIELD_NUMBER: _ClassVar[int]
    IS_AUTH_FIELD_NUMBER: _ClassVar[int]
    IS_VERIFIED_FIELD_NUMBER: _ClassVar[int]
    is_custody: bool
    is_auth: bool
    is_verified: bool
    def __init__(self, is_custody: bool = ..., is_auth: bool = ..., is_verified: bool = ...) -> None: ...

class ContactInfoBody(_message.Message):
    __slots__ = ("gossip_address", "peer_id", "snapchain_version", "network", "timestamp", "announce_rpc_address")
    GOSSIP_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    PEER_ID_FIELD_NUMBER: _ClassVar[int]
    SNAPCHAIN_VERSION_FIELD_NUMBER: _ClassVar[int]
    NETWORK_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    ANNOUNCE_RPC_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    gossip_address: str
    peer_id: bytes
    snapchain_version: str
    network: _message_pb2.FarcasterNetwork
    timestamp: int
    announce_rpc_address: str
    def __init__(self, gossip_address: _Optional[str] = ..., peer_id: _Optional[bytes] = ..., snapchain_version: _Optional[str] = ..., network: _Optional[_Union[_message_pb2.FarcasterNetwork, str]] = ..., timestamp: _Optional[int] = ..., announce_rpc_address: _Optional[str] = ...) -> None: ...

class GetConnectedPeersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetConnectedPeersResponse(_message.Message):
    __slots__ = ("contacts",)
    CONTACTS_FIELD_NUMBER: _ClassVar[int]
    contacts: _containers.RepeatedCompositeFieldContainer[ContactInfoBody]
    def __init__(self, contacts: _Optional[_Iterable[_Union[ContactInfoBody, _Mapping]]] = ...) -> None: ...
