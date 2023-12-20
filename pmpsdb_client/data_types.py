"""
This module defines important data structures centrally.

This helps us compare the same kinds of data to each other,
even when this data comes from different sources.

Note that all the dataclasses are frozen: editing these data
structures is not in scope for this library, it is only intended
to move these files around and compare them to each other.
"""
import dataclasses
import datetime
import enum
import typing

from pcdscalc.pmps import get_bitmask_desc

from .beam_class import summarize_beam_class_bitmask

# "Raw" data types are the presentation of the data as in the json file.
# Most beam params are serialized as str, except for id (int) and special (bool)
RawStateBeamParams = dict[str, typing.Union[str, int, bool]]
# A bunch of raw beam params are collected by name for one device
RawDeviceBeamParams = dict[str, RawStateBeamParams]
# Each device on the plc is collected by name
RawPLCBeamParams = dict[str, RawDeviceBeamParams]
# The json file has the plc name at the top level
RawFileContents = dict[str, RawPLCBeamParams]

T = typing.TypeVar("T")


class BPKeys(enum.Enum):
    """
    Mapping from user-visible name to database key for beam parameters.
    """
    id = "id"
    name_ = "name"
    beamline = "beamline"
    nbc_range = "nBeamClassRange"
    nev_range = "neVRange"
    ntran = "nTran"
    nrate = "nRate"
    aperture_name = "ap_name"
    y_gap = "ap_ygap"
    y_center = "ap_ycenter"
    x_gap = "ap_xgap"
    x_center = "ap_xcenter"
    damage_limit = "damage_limit"
    pulse_energy = "pulse_energy"
    notes = "notes"
    special = "special"


@dataclasses.dataclass(frozen=True)
class BeamParameters:
    """
    Struct representation of one state's beam parameters.

    The raw data has most of these as strings, but to make the struct
    here we'll convert them to the most natural data types for
    comparisons and add additional helpful fields for
    human readability.

    The same names as used in the web application are used here,
    but all lowercase and with spaces replaced with underscores.
    """
    id: int
    name: str
    beamline: str
    nbc_range: int
    nbc_range_mask: str
    nbc_range_desc: str
    nev_range: int
    nev_range_mask: str
    nev_range_desc: str
    ntran: float
    nrate: int
    aperture_name: str
    y_gap: float
    y_center: float
    x_gap: float
    x_center: float
    damage_limit: str
    pulse_energy: str
    notes: str
    special: bool

    @classmethod
    def from_raw(cls: type[T], data: RawStateBeamParams) -> T:
        return cls(
            id=data[BPKeys.id],
            name=data[BPKeys.name_],
            beamline=data[BPKeys.beamline],
            nbc_range=int(data[BPKeys.nbc_range]),
            nbc_range_mask=data[BPKeys.nbc_range],
            nbc_range_desc=summarize_beam_class_bitmask(int(data[BPKeys.nbc_range])),
            nev_range=int(data[BPKeys.nev_range]),
            nev_range_mask=data[BPKeys.nev_range],
            nev_range_desc=get_bitmask_desc(data[BPKeys.nev_range]),
            ntran=float(data[BPKeys.ntran]),
            aperture_name=data[BPKeys.aperture_name],
            y_gap=float(data[BPKeys.y_gap]),
            y_center=float(data[BPKeys.y_center]),
            x_gap=float(data[BPKeys.x_gap]),
            x_center=float(data[BPKeys.x_center]),
            damage_limit=data[BPKeys.damage_limit],
            pulse_energy=data[BPKeys.pulse_energy],
            notes=data[BPKeys.notes],
            special=data[BPKeys.special],
        )


@dataclasses.dataclass(frozen=True)
class DeviceBeamParams:
    """
    The beam parameters associated with one device.

    One device may have an arbitrary number of states.
    """
    device_name: str
    state_beam_params: dict[str, BeamParameters]

    @classmethod
    def from_raw(cls: type[T], device_name: str, data: RawDeviceBeamParams) -> T:
        return cls(
            device_name=device_name,
            state_beam_params={
                key: BeamParameters.from_raw(value)
                for key, value in data.items()
            }
        )


@dataclasses.dataclass(frozen=True)
class FileContents:
    """
    The contents of one file.

    Each file is associated with exactly one plc hostname
    and can contain an arbitrary number of devices.
    """
    plc_name: str
    device_beam_params: dict[str, DeviceBeamParams]

    @classmethod
    def from_raw(cls: type[T], data: RawFileContents) -> T:
        return cls(
            plc_name=next(data.keys()),
            device_beam_params={
                key: DeviceBeamParams.from_raw(key, value)
                for key, value in data.items()
            }
        )


@dataclasses.dataclass(frozen=True)
class FileInfo:
    """
    Generalized file info.

    The fields are based on *nix systems, but this will
    also be used for windows systems too.

    This class has no constructor helpers here.
    Each data source will need to implement a unique
    constructor for this.
    """
    filename: str
    directory: str
    server: str
    is_directory: bool
    permissions: str
    links: int
    user: str
    group: str
    size: int
    last_changed: datetime.datetime
    raw_contents: RawFileContents
    contents: FileContents
