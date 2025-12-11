from . import username_proof_pb2  as _username_proof_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class HashScheme(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HASH_SCHEME_NONE: _ClassVar[HashScheme]
    HASH_SCHEME_BLAKE3: _ClassVar[HashScheme]

class SignatureScheme(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SIGNATURE_SCHEME_NONE: _ClassVar[SignatureScheme]
    SIGNATURE_SCHEME_ED25519: _ClassVar[SignatureScheme]
    SIGNATURE_SCHEME_EIP712: _ClassVar[SignatureScheme]

class MessageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MESSAGE_TYPE_NONE: _ClassVar[MessageType]
    MESSAGE_TYPE_CAST_ADD: _ClassVar[MessageType]
    MESSAGE_TYPE_CAST_REMOVE: _ClassVar[MessageType]
    MESSAGE_TYPE_REACTION_ADD: _ClassVar[MessageType]
    MESSAGE_TYPE_REACTION_REMOVE: _ClassVar[MessageType]
    MESSAGE_TYPE_LINK_ADD: _ClassVar[MessageType]
    MESSAGE_TYPE_LINK_REMOVE: _ClassVar[MessageType]
    MESSAGE_TYPE_VERIFICATION_ADD_ETH_ADDRESS: _ClassVar[MessageType]
    MESSAGE_TYPE_VERIFICATION_REMOVE: _ClassVar[MessageType]
    MESSAGE_TYPE_USER_DATA_ADD: _ClassVar[MessageType]
    MESSAGE_TYPE_USERNAME_PROOF: _ClassVar[MessageType]
    MESSAGE_TYPE_FRAME_ACTION: _ClassVar[MessageType]
    MESSAGE_TYPE_LINK_COMPACT_STATE: _ClassVar[MessageType]
    MESSAGE_TYPE_LEND_STORAGE: _ClassVar[MessageType]

class FarcasterNetwork(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FARCASTER_NETWORK_NONE: _ClassVar[FarcasterNetwork]
    FARCASTER_NETWORK_MAINNET: _ClassVar[FarcasterNetwork]
    FARCASTER_NETWORK_TESTNET: _ClassVar[FarcasterNetwork]
    FARCASTER_NETWORK_DEVNET: _ClassVar[FarcasterNetwork]

class UserDataType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    USER_DATA_TYPE_NONE: _ClassVar[UserDataType]
    USER_DATA_TYPE_PFP: _ClassVar[UserDataType]
    USER_DATA_TYPE_DISPLAY: _ClassVar[UserDataType]
    USER_DATA_TYPE_BIO: _ClassVar[UserDataType]
    USER_DATA_TYPE_URL: _ClassVar[UserDataType]
    USER_DATA_TYPE_USERNAME: _ClassVar[UserDataType]
    USER_DATA_TYPE_LOCATION: _ClassVar[UserDataType]
    USER_DATA_TYPE_TWITTER: _ClassVar[UserDataType]
    USER_DATA_TYPE_GITHUB: _ClassVar[UserDataType]
    USER_DATA_TYPE_BANNER: _ClassVar[UserDataType]
    USER_DATA_PRIMARY_ADDRESS_ETHEREUM: _ClassVar[UserDataType]
    USER_DATA_PRIMARY_ADDRESS_SOLANA: _ClassVar[UserDataType]
    USER_DATA_TYPE_PROFILE_TOKEN: _ClassVar[UserDataType]

class CastType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CAST: _ClassVar[CastType]
    LONG_CAST: _ClassVar[CastType]
    TEN_K_CAST: _ClassVar[CastType]

class ReactionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    REACTION_TYPE_NONE: _ClassVar[ReactionType]
    REACTION_TYPE_LIKE: _ClassVar[ReactionType]
    REACTION_TYPE_RECAST: _ClassVar[ReactionType]

class Protocol(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROTOCOL_ETHEREUM: _ClassVar[Protocol]
    PROTOCOL_SOLANA: _ClassVar[Protocol]

class StorageUnitType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNIT_TYPE_LEGACY: _ClassVar[StorageUnitType]
    UNIT_TYPE_2024: _ClassVar[StorageUnitType]
    UNIT_TYPE_2025: _ClassVar[StorageUnitType]
HASH_SCHEME_NONE: HashScheme
HASH_SCHEME_BLAKE3: HashScheme
SIGNATURE_SCHEME_NONE: SignatureScheme
SIGNATURE_SCHEME_ED25519: SignatureScheme
SIGNATURE_SCHEME_EIP712: SignatureScheme
MESSAGE_TYPE_NONE: MessageType
MESSAGE_TYPE_CAST_ADD: MessageType
MESSAGE_TYPE_CAST_REMOVE: MessageType
MESSAGE_TYPE_REACTION_ADD: MessageType
MESSAGE_TYPE_REACTION_REMOVE: MessageType
MESSAGE_TYPE_LINK_ADD: MessageType
MESSAGE_TYPE_LINK_REMOVE: MessageType
MESSAGE_TYPE_VERIFICATION_ADD_ETH_ADDRESS: MessageType
MESSAGE_TYPE_VERIFICATION_REMOVE: MessageType
MESSAGE_TYPE_USER_DATA_ADD: MessageType
MESSAGE_TYPE_USERNAME_PROOF: MessageType
MESSAGE_TYPE_FRAME_ACTION: MessageType
MESSAGE_TYPE_LINK_COMPACT_STATE: MessageType
MESSAGE_TYPE_LEND_STORAGE: MessageType
FARCASTER_NETWORK_NONE: FarcasterNetwork
FARCASTER_NETWORK_MAINNET: FarcasterNetwork
FARCASTER_NETWORK_TESTNET: FarcasterNetwork
FARCASTER_NETWORK_DEVNET: FarcasterNetwork
USER_DATA_TYPE_NONE: UserDataType
USER_DATA_TYPE_PFP: UserDataType
USER_DATA_TYPE_DISPLAY: UserDataType
USER_DATA_TYPE_BIO: UserDataType
USER_DATA_TYPE_URL: UserDataType
USER_DATA_TYPE_USERNAME: UserDataType
USER_DATA_TYPE_LOCATION: UserDataType
USER_DATA_TYPE_TWITTER: UserDataType
USER_DATA_TYPE_GITHUB: UserDataType
USER_DATA_TYPE_BANNER: UserDataType
USER_DATA_PRIMARY_ADDRESS_ETHEREUM: UserDataType
USER_DATA_PRIMARY_ADDRESS_SOLANA: UserDataType
USER_DATA_TYPE_PROFILE_TOKEN: UserDataType
CAST: CastType
LONG_CAST: CastType
TEN_K_CAST: CastType
REACTION_TYPE_NONE: ReactionType
REACTION_TYPE_LIKE: ReactionType
REACTION_TYPE_RECAST: ReactionType
PROTOCOL_ETHEREUM: Protocol
PROTOCOL_SOLANA: Protocol
UNIT_TYPE_LEGACY: StorageUnitType
UNIT_TYPE_2024: StorageUnitType
UNIT_TYPE_2025: StorageUnitType

class Message(_message.Message):
    __slots__ = ("data", "hash", "hash_scheme", "signature", "signature_scheme", "signer", "data_bytes")
    DATA_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    HASH_SCHEME_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_SCHEME_FIELD_NUMBER: _ClassVar[int]
    SIGNER_FIELD_NUMBER: _ClassVar[int]
    DATA_BYTES_FIELD_NUMBER: _ClassVar[int]
    data: MessageData
    hash: bytes
    hash_scheme: HashScheme
    signature: bytes
    signature_scheme: SignatureScheme
    signer: bytes
    data_bytes: bytes
    def __init__(self, data: _Optional[_Union[MessageData, _Mapping]] = ..., hash: _Optional[bytes] = ..., hash_scheme: _Optional[_Union[HashScheme, str]] = ..., signature: _Optional[bytes] = ..., signature_scheme: _Optional[_Union[SignatureScheme, str]] = ..., signer: _Optional[bytes] = ..., data_bytes: _Optional[bytes] = ...) -> None: ...

class MessageData(_message.Message):
    __slots__ = ("type", "fid", "timestamp", "network", "cast_add_body", "cast_remove_body", "reaction_body", "verification_add_address_body", "verification_remove_body", "user_data_body", "link_body", "username_proof_body", "frame_action_body", "link_compact_state_body", "lend_storage_body")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    FID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    NETWORK_FIELD_NUMBER: _ClassVar[int]
    CAST_ADD_BODY_FIELD_NUMBER: _ClassVar[int]
    CAST_REMOVE_BODY_FIELD_NUMBER: _ClassVar[int]
    REACTION_BODY_FIELD_NUMBER: _ClassVar[int]
    VERIFICATION_ADD_ADDRESS_BODY_FIELD_NUMBER: _ClassVar[int]
    VERIFICATION_REMOVE_BODY_FIELD_NUMBER: _ClassVar[int]
    USER_DATA_BODY_FIELD_NUMBER: _ClassVar[int]
    LINK_BODY_FIELD_NUMBER: _ClassVar[int]
    USERNAME_PROOF_BODY_FIELD_NUMBER: _ClassVar[int]
    FRAME_ACTION_BODY_FIELD_NUMBER: _ClassVar[int]
    LINK_COMPACT_STATE_BODY_FIELD_NUMBER: _ClassVar[int]
    LEND_STORAGE_BODY_FIELD_NUMBER: _ClassVar[int]
    type: MessageType
    fid: int
    timestamp: int
    network: FarcasterNetwork
    cast_add_body: CastAddBody
    cast_remove_body: CastRemoveBody
    reaction_body: ReactionBody
    verification_add_address_body: VerificationAddAddressBody
    verification_remove_body: VerificationRemoveBody
    user_data_body: UserDataBody
    link_body: LinkBody
    username_proof_body: _username_proof_pb2.UserNameProof
    frame_action_body: FrameActionBody
    link_compact_state_body: LinkCompactStateBody
    lend_storage_body: LendStorageBody
    def __init__(self, type: _Optional[_Union[MessageType, str]] = ..., fid: _Optional[int] = ..., timestamp: _Optional[int] = ..., network: _Optional[_Union[FarcasterNetwork, str]] = ..., cast_add_body: _Optional[_Union[CastAddBody, _Mapping]] = ..., cast_remove_body: _Optional[_Union[CastRemoveBody, _Mapping]] = ..., reaction_body: _Optional[_Union[ReactionBody, _Mapping]] = ..., verification_add_address_body: _Optional[_Union[VerificationAddAddressBody, _Mapping]] = ..., verification_remove_body: _Optional[_Union[VerificationRemoveBody, _Mapping]] = ..., user_data_body: _Optional[_Union[UserDataBody, _Mapping]] = ..., link_body: _Optional[_Union[LinkBody, _Mapping]] = ..., username_proof_body: _Optional[_Union[_username_proof_pb2.UserNameProof, _Mapping]] = ..., frame_action_body: _Optional[_Union[FrameActionBody, _Mapping]] = ..., link_compact_state_body: _Optional[_Union[LinkCompactStateBody, _Mapping]] = ..., lend_storage_body: _Optional[_Union[LendStorageBody, _Mapping]] = ...) -> None: ...

class UserDataBody(_message.Message):
    __slots__ = ("type", "value")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    type: UserDataType
    value: str
    def __init__(self, type: _Optional[_Union[UserDataType, str]] = ..., value: _Optional[str] = ...) -> None: ...

class Embed(_message.Message):
    __slots__ = ("url", "cast_id")
    URL_FIELD_NUMBER: _ClassVar[int]
    CAST_ID_FIELD_NUMBER: _ClassVar[int]
    url: str
    cast_id: CastId
    def __init__(self, url: _Optional[str] = ..., cast_id: _Optional[_Union[CastId, _Mapping]] = ...) -> None: ...

class CastAddBody(_message.Message):
    __slots__ = ("embeds_deprecated", "mentions", "parent_cast_id", "parent_url", "text", "mentions_positions", "embeds", "type")
    EMBEDS_DEPRECATED_FIELD_NUMBER: _ClassVar[int]
    MENTIONS_FIELD_NUMBER: _ClassVar[int]
    PARENT_CAST_ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_URL_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    MENTIONS_POSITIONS_FIELD_NUMBER: _ClassVar[int]
    EMBEDS_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    embeds_deprecated: _containers.RepeatedScalarFieldContainer[str]
    mentions: _containers.RepeatedScalarFieldContainer[int]
    parent_cast_id: CastId
    parent_url: str
    text: str
    mentions_positions: _containers.RepeatedScalarFieldContainer[int]
    embeds: _containers.RepeatedCompositeFieldContainer[Embed]
    type: CastType
    def __init__(self, embeds_deprecated: _Optional[_Iterable[str]] = ..., mentions: _Optional[_Iterable[int]] = ..., parent_cast_id: _Optional[_Union[CastId, _Mapping]] = ..., parent_url: _Optional[str] = ..., text: _Optional[str] = ..., mentions_positions: _Optional[_Iterable[int]] = ..., embeds: _Optional[_Iterable[_Union[Embed, _Mapping]]] = ..., type: _Optional[_Union[CastType, str]] = ...) -> None: ...

class CastRemoveBody(_message.Message):
    __slots__ = ("target_hash",)
    TARGET_HASH_FIELD_NUMBER: _ClassVar[int]
    target_hash: bytes
    def __init__(self, target_hash: _Optional[bytes] = ...) -> None: ...

class CastId(_message.Message):
    __slots__ = ("fid", "hash")
    FID_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    fid: int
    hash: bytes
    def __init__(self, fid: _Optional[int] = ..., hash: _Optional[bytes] = ...) -> None: ...

class ReactionBody(_message.Message):
    __slots__ = ("type", "target_cast_id", "target_url")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    TARGET_CAST_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_URL_FIELD_NUMBER: _ClassVar[int]
    type: ReactionType
    target_cast_id: CastId
    target_url: str
    def __init__(self, type: _Optional[_Union[ReactionType, str]] = ..., target_cast_id: _Optional[_Union[CastId, _Mapping]] = ..., target_url: _Optional[str] = ...) -> None: ...

class VerificationAddAddressBody(_message.Message):
    __slots__ = ("address", "claim_signature", "block_hash", "verification_type", "chain_id", "protocol")
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    CLAIM_SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    BLOCK_HASH_FIELD_NUMBER: _ClassVar[int]
    VERIFICATION_TYPE_FIELD_NUMBER: _ClassVar[int]
    CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    address: bytes
    claim_signature: bytes
    block_hash: bytes
    verification_type: int
    chain_id: int
    protocol: Protocol
    def __init__(self, address: _Optional[bytes] = ..., claim_signature: _Optional[bytes] = ..., block_hash: _Optional[bytes] = ..., verification_type: _Optional[int] = ..., chain_id: _Optional[int] = ..., protocol: _Optional[_Union[Protocol, str]] = ...) -> None: ...

class VerificationRemoveBody(_message.Message):
    __slots__ = ("address", "protocol")
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    address: bytes
    protocol: Protocol
    def __init__(self, address: _Optional[bytes] = ..., protocol: _Optional[_Union[Protocol, str]] = ...) -> None: ...

class LinkBody(_message.Message):
    __slots__ = ("type", "displayTimestamp", "target_fid")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DISPLAYTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    TARGET_FID_FIELD_NUMBER: _ClassVar[int]
    type: str
    displayTimestamp: int
    target_fid: int
    def __init__(self, type: _Optional[str] = ..., displayTimestamp: _Optional[int] = ..., target_fid: _Optional[int] = ...) -> None: ...

class LinkCompactStateBody(_message.Message):
    __slots__ = ("type", "target_fids")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIDS_FIELD_NUMBER: _ClassVar[int]
    type: str
    target_fids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, type: _Optional[str] = ..., target_fids: _Optional[_Iterable[int]] = ...) -> None: ...

class FrameActionBody(_message.Message):
    __slots__ = ("url", "button_index", "cast_id", "input_text", "state", "transaction_id", "address")
    URL_FIELD_NUMBER: _ClassVar[int]
    BUTTON_INDEX_FIELD_NUMBER: _ClassVar[int]
    CAST_ID_FIELD_NUMBER: _ClassVar[int]
    INPUT_TEXT_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    url: bytes
    button_index: int
    cast_id: CastId
    input_text: bytes
    state: bytes
    transaction_id: bytes
    address: bytes
    def __init__(self, url: _Optional[bytes] = ..., button_index: _Optional[int] = ..., cast_id: _Optional[_Union[CastId, _Mapping]] = ..., input_text: _Optional[bytes] = ..., state: _Optional[bytes] = ..., transaction_id: _Optional[bytes] = ..., address: _Optional[bytes] = ...) -> None: ...

class LendStorageBody(_message.Message):
    __slots__ = ("to_fid", "num_units", "unit_type")
    TO_FID_FIELD_NUMBER: _ClassVar[int]
    NUM_UNITS_FIELD_NUMBER: _ClassVar[int]
    UNIT_TYPE_FIELD_NUMBER: _ClassVar[int]
    to_fid: int
    num_units: int
    unit_type: StorageUnitType
    def __init__(self, to_fid: _Optional[int] = ..., num_units: _Optional[int] = ..., unit_type: _Optional[_Union[StorageUnitType, str]] = ...) -> None: ...
