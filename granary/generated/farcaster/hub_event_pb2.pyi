from . import message_pb2  as _message_pb2
from . import onchain_event_pb2  as _onchain_event_pb2
from . import username_proof_pb2  as _username_proof_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class HubEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HUB_EVENT_TYPE_NONE: _ClassVar[HubEventType]
    HUB_EVENT_TYPE_MERGE_MESSAGE: _ClassVar[HubEventType]
    HUB_EVENT_TYPE_PRUNE_MESSAGE: _ClassVar[HubEventType]
    HUB_EVENT_TYPE_REVOKE_MESSAGE: _ClassVar[HubEventType]
    HUB_EVENT_TYPE_MERGE_USERNAME_PROOF: _ClassVar[HubEventType]
    HUB_EVENT_TYPE_MERGE_ON_CHAIN_EVENT: _ClassVar[HubEventType]
    HUB_EVENT_TYPE_MERGE_FAILURE: _ClassVar[HubEventType]
    HUB_EVENT_TYPE_BLOCK_CONFIRMED: _ClassVar[HubEventType]
HUB_EVENT_TYPE_NONE: HubEventType
HUB_EVENT_TYPE_MERGE_MESSAGE: HubEventType
HUB_EVENT_TYPE_PRUNE_MESSAGE: HubEventType
HUB_EVENT_TYPE_REVOKE_MESSAGE: HubEventType
HUB_EVENT_TYPE_MERGE_USERNAME_PROOF: HubEventType
HUB_EVENT_TYPE_MERGE_ON_CHAIN_EVENT: HubEventType
HUB_EVENT_TYPE_MERGE_FAILURE: HubEventType
HUB_EVENT_TYPE_BLOCK_CONFIRMED: HubEventType

class MergeMessageBody(_message.Message):
    __slots__ = ("message", "deleted_messages")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DELETED_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    message: _message_pb2.Message
    deleted_messages: _containers.RepeatedCompositeFieldContainer[_message_pb2.Message]
    def __init__(self, message: _Optional[_Union[_message_pb2.Message, _Mapping]] = ..., deleted_messages: _Optional[_Iterable[_Union[_message_pb2.Message, _Mapping]]] = ...) -> None: ...

class MergeFailureBody(_message.Message):
    __slots__ = ("message", "code", "reason")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    message: _message_pb2.Message
    code: str
    reason: str
    def __init__(self, message: _Optional[_Union[_message_pb2.Message, _Mapping]] = ..., code: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class PruneMessageBody(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: _message_pb2.Message
    def __init__(self, message: _Optional[_Union[_message_pb2.Message, _Mapping]] = ...) -> None: ...

class RevokeMessageBody(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: _message_pb2.Message
    def __init__(self, message: _Optional[_Union[_message_pb2.Message, _Mapping]] = ...) -> None: ...

class BlockConfirmedBody(_message.Message):
    __slots__ = ("block_number", "shard_index", "timestamp", "block_hash", "total_events", "event_counts_by_type", "max_block_event_seqnum")
    class EventCountsByTypeEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: int
        def __init__(self, key: _Optional[int] = ..., value: _Optional[int] = ...) -> None: ...
    BLOCK_NUMBER_FIELD_NUMBER: _ClassVar[int]
    SHARD_INDEX_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    BLOCK_HASH_FIELD_NUMBER: _ClassVar[int]
    TOTAL_EVENTS_FIELD_NUMBER: _ClassVar[int]
    EVENT_COUNTS_BY_TYPE_FIELD_NUMBER: _ClassVar[int]
    MAX_BLOCK_EVENT_SEQNUM_FIELD_NUMBER: _ClassVar[int]
    block_number: int
    shard_index: int
    timestamp: int
    block_hash: bytes
    total_events: int
    event_counts_by_type: _containers.ScalarMap[int, int]
    max_block_event_seqnum: int
    def __init__(self, block_number: _Optional[int] = ..., shard_index: _Optional[int] = ..., timestamp: _Optional[int] = ..., block_hash: _Optional[bytes] = ..., total_events: _Optional[int] = ..., event_counts_by_type: _Optional[_Mapping[int, int]] = ..., max_block_event_seqnum: _Optional[int] = ...) -> None: ...

class MergeOnChainEventBody(_message.Message):
    __slots__ = ("on_chain_event",)
    ON_CHAIN_EVENT_FIELD_NUMBER: _ClassVar[int]
    on_chain_event: _onchain_event_pb2.OnChainEvent
    def __init__(self, on_chain_event: _Optional[_Union[_onchain_event_pb2.OnChainEvent, _Mapping]] = ...) -> None: ...

class MergeUserNameProofBody(_message.Message):
    __slots__ = ("username_proof", "deleted_username_proof", "username_proof_message", "deleted_username_proof_message")
    USERNAME_PROOF_FIELD_NUMBER: _ClassVar[int]
    DELETED_USERNAME_PROOF_FIELD_NUMBER: _ClassVar[int]
    USERNAME_PROOF_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DELETED_USERNAME_PROOF_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    username_proof: _username_proof_pb2.UserNameProof
    deleted_username_proof: _username_proof_pb2.UserNameProof
    username_proof_message: _message_pb2.Message
    deleted_username_proof_message: _message_pb2.Message
    def __init__(self, username_proof: _Optional[_Union[_username_proof_pb2.UserNameProof, _Mapping]] = ..., deleted_username_proof: _Optional[_Union[_username_proof_pb2.UserNameProof, _Mapping]] = ..., username_proof_message: _Optional[_Union[_message_pb2.Message, _Mapping]] = ..., deleted_username_proof_message: _Optional[_Union[_message_pb2.Message, _Mapping]] = ...) -> None: ...

class HubEvent(_message.Message):
    __slots__ = ("type", "id", "merge_message_body", "prune_message_body", "revoke_message_body", "merge_username_proof_body", "merge_on_chain_event_body", "merge_failure", "block_confirmed_body", "block_number", "shard_index", "timestamp")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    MERGE_MESSAGE_BODY_FIELD_NUMBER: _ClassVar[int]
    PRUNE_MESSAGE_BODY_FIELD_NUMBER: _ClassVar[int]
    REVOKE_MESSAGE_BODY_FIELD_NUMBER: _ClassVar[int]
    MERGE_USERNAME_PROOF_BODY_FIELD_NUMBER: _ClassVar[int]
    MERGE_ON_CHAIN_EVENT_BODY_FIELD_NUMBER: _ClassVar[int]
    MERGE_FAILURE_FIELD_NUMBER: _ClassVar[int]
    BLOCK_CONFIRMED_BODY_FIELD_NUMBER: _ClassVar[int]
    BLOCK_NUMBER_FIELD_NUMBER: _ClassVar[int]
    SHARD_INDEX_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    type: HubEventType
    id: int
    merge_message_body: MergeMessageBody
    prune_message_body: PruneMessageBody
    revoke_message_body: RevokeMessageBody
    merge_username_proof_body: MergeUserNameProofBody
    merge_on_chain_event_body: MergeOnChainEventBody
    merge_failure: MergeFailureBody
    block_confirmed_body: BlockConfirmedBody
    block_number: int
    shard_index: int
    timestamp: int
    def __init__(self, type: _Optional[_Union[HubEventType, str]] = ..., id: _Optional[int] = ..., merge_message_body: _Optional[_Union[MergeMessageBody, _Mapping]] = ..., prune_message_body: _Optional[_Union[PruneMessageBody, _Mapping]] = ..., revoke_message_body: _Optional[_Union[RevokeMessageBody, _Mapping]] = ..., merge_username_proof_body: _Optional[_Union[MergeUserNameProofBody, _Mapping]] = ..., merge_on_chain_event_body: _Optional[_Union[MergeOnChainEventBody, _Mapping]] = ..., merge_failure: _Optional[_Union[MergeFailureBody, _Mapping]] = ..., block_confirmed_body: _Optional[_Union[BlockConfirmedBody, _Mapping]] = ..., block_number: _Optional[int] = ..., shard_index: _Optional[int] = ..., timestamp: _Optional[int] = ...) -> None: ...
