from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OnChainEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EVENT_TYPE_NONE: _ClassVar[OnChainEventType]
    EVENT_TYPE_SIGNER: _ClassVar[OnChainEventType]
    EVENT_TYPE_SIGNER_MIGRATED: _ClassVar[OnChainEventType]
    EVENT_TYPE_ID_REGISTER: _ClassVar[OnChainEventType]
    EVENT_TYPE_STORAGE_RENT: _ClassVar[OnChainEventType]
    EVENT_TYPE_TIER_PURCHASE: _ClassVar[OnChainEventType]

class TierType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    None: _ClassVar[TierType]
    Pro: _ClassVar[TierType]

class SignerEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SIGNER_EVENT_TYPE_NONE: _ClassVar[SignerEventType]
    SIGNER_EVENT_TYPE_ADD: _ClassVar[SignerEventType]
    SIGNER_EVENT_TYPE_REMOVE: _ClassVar[SignerEventType]
    SIGNER_EVENT_TYPE_ADMIN_RESET: _ClassVar[SignerEventType]

class IdRegisterEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ID_REGISTER_EVENT_TYPE_NONE: _ClassVar[IdRegisterEventType]
    ID_REGISTER_EVENT_TYPE_REGISTER: _ClassVar[IdRegisterEventType]
    ID_REGISTER_EVENT_TYPE_TRANSFER: _ClassVar[IdRegisterEventType]
    ID_REGISTER_EVENT_TYPE_CHANGE_RECOVERY: _ClassVar[IdRegisterEventType]
EVENT_TYPE_NONE: OnChainEventType
EVENT_TYPE_SIGNER: OnChainEventType
EVENT_TYPE_SIGNER_MIGRATED: OnChainEventType
EVENT_TYPE_ID_REGISTER: OnChainEventType
EVENT_TYPE_STORAGE_RENT: OnChainEventType
EVENT_TYPE_TIER_PURCHASE: OnChainEventType
None: TierType
Pro: TierType
SIGNER_EVENT_TYPE_NONE: SignerEventType
SIGNER_EVENT_TYPE_ADD: SignerEventType
SIGNER_EVENT_TYPE_REMOVE: SignerEventType
SIGNER_EVENT_TYPE_ADMIN_RESET: SignerEventType
ID_REGISTER_EVENT_TYPE_NONE: IdRegisterEventType
ID_REGISTER_EVENT_TYPE_REGISTER: IdRegisterEventType
ID_REGISTER_EVENT_TYPE_TRANSFER: IdRegisterEventType
ID_REGISTER_EVENT_TYPE_CHANGE_RECOVERY: IdRegisterEventType

class OnChainEvent(_message.Message):
    __slots__ = ("type", "chain_id", "block_number", "block_hash", "block_timestamp", "transaction_hash", "log_index", "fid", "signer_event_body", "signer_migrated_event_body", "id_register_event_body", "storage_rent_event_body", "tier_purchase_event_body", "tx_index", "version")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_NUMBER_FIELD_NUMBER: _ClassVar[int]
    BLOCK_HASH_FIELD_NUMBER: _ClassVar[int]
    BLOCK_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    TRANSACTION_HASH_FIELD_NUMBER: _ClassVar[int]
    LOG_INDEX_FIELD_NUMBER: _ClassVar[int]
    FID_FIELD_NUMBER: _ClassVar[int]
    SIGNER_EVENT_BODY_FIELD_NUMBER: _ClassVar[int]
    SIGNER_MIGRATED_EVENT_BODY_FIELD_NUMBER: _ClassVar[int]
    ID_REGISTER_EVENT_BODY_FIELD_NUMBER: _ClassVar[int]
    STORAGE_RENT_EVENT_BODY_FIELD_NUMBER: _ClassVar[int]
    TIER_PURCHASE_EVENT_BODY_FIELD_NUMBER: _ClassVar[int]
    TX_INDEX_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    type: OnChainEventType
    chain_id: int
    block_number: int
    block_hash: bytes
    block_timestamp: int
    transaction_hash: bytes
    log_index: int
    fid: int
    signer_event_body: SignerEventBody
    signer_migrated_event_body: SignerMigratedEventBody
    id_register_event_body: IdRegisterEventBody
    storage_rent_event_body: StorageRentEventBody
    tier_purchase_event_body: TierPurchaseBody
    tx_index: int
    version: int
    def __init__(self, type: _Optional[_Union[OnChainEventType, str]] = ..., chain_id: _Optional[int] = ..., block_number: _Optional[int] = ..., block_hash: _Optional[bytes] = ..., block_timestamp: _Optional[int] = ..., transaction_hash: _Optional[bytes] = ..., log_index: _Optional[int] = ..., fid: _Optional[int] = ..., signer_event_body: _Optional[_Union[SignerEventBody, _Mapping]] = ..., signer_migrated_event_body: _Optional[_Union[SignerMigratedEventBody, _Mapping]] = ..., id_register_event_body: _Optional[_Union[IdRegisterEventBody, _Mapping]] = ..., storage_rent_event_body: _Optional[_Union[StorageRentEventBody, _Mapping]] = ..., tier_purchase_event_body: _Optional[_Union[TierPurchaseBody, _Mapping]] = ..., tx_index: _Optional[int] = ..., version: _Optional[int] = ...) -> None: ...

class TierPurchaseBody(_message.Message):
    __slots__ = ("tier_type", "for_days", "payer")
    TIER_TYPE_FIELD_NUMBER: _ClassVar[int]
    FOR_DAYS_FIELD_NUMBER: _ClassVar[int]
    PAYER_FIELD_NUMBER: _ClassVar[int]
    tier_type: TierType
    for_days: int
    payer: bytes
    def __init__(self, tier_type: _Optional[_Union[TierType, str]] = ..., for_days: _Optional[int] = ..., payer: _Optional[bytes] = ...) -> None: ...

class SignerEventBody(_message.Message):
    __slots__ = ("key", "key_type", "event_type", "metadata", "metadata_type")
    KEY_FIELD_NUMBER: _ClassVar[int]
    KEY_TYPE_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    METADATA_TYPE_FIELD_NUMBER: _ClassVar[int]
    key: bytes
    key_type: int
    event_type: SignerEventType
    metadata: bytes
    metadata_type: int
    def __init__(self, key: _Optional[bytes] = ..., key_type: _Optional[int] = ..., event_type: _Optional[_Union[SignerEventType, str]] = ..., metadata: _Optional[bytes] = ..., metadata_type: _Optional[int] = ...) -> None: ...

class SignerMigratedEventBody(_message.Message):
    __slots__ = ("migratedAt",)
    MIGRATEDAT_FIELD_NUMBER: _ClassVar[int]
    migratedAt: int
    def __init__(self, migratedAt: _Optional[int] = ...) -> None: ...

class IdRegisterEventBody(_message.Message):
    __slots__ = ("to", "event_type", "recovery_address")
    TO_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    FROM_FIELD_NUMBER: _ClassVar[int]
    RECOVERY_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    to: bytes
    event_type: IdRegisterEventType
    recovery_address: bytes
    def __init__(self, to: _Optional[bytes] = ..., event_type: _Optional[_Union[IdRegisterEventType, str]] = ..., recovery_address: _Optional[bytes] = ..., **kwargs) -> None: ...

class StorageRentEventBody(_message.Message):
    __slots__ = ("payer", "units", "expiry")
    PAYER_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    EXPIRY_FIELD_NUMBER: _ClassVar[int]
    payer: bytes
    units: int
    expiry: int
    def __init__(self, payer: _Optional[bytes] = ..., units: _Optional[int] = ..., expiry: _Optional[int] = ...) -> None: ...
