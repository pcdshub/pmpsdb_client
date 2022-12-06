from typing import Any

from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal, EpicsSignalRO


class PLCDBControls(Device):
    """
    Manipulate or monitor the PLC's DB loading.

    The prefix should be the PLC's prefix, e.g.:
    PLC:LFE:MOTION
    PLC:TST:MOT

    And is not guaranteed to be consistent between PLCs.
    """
    refresh = Cpt(
        EpicsSignal,
        'DB:REFRESH_RBV',
        write_pv='DB:REFRESH',
        doc='Cause the PLC to re-read from the database file.',
    )
    last_refresh = Cpt(
        EpicsSignalRO,
        'DB:LAST_REFRESH_RBV',
        doc='UNIX timestamp of the last file re-read.'
    )


class StateBeamParameters(Device):
    """
    The beam parameters associated with one state position.

    This represents the elements from ST_BeamParams that match up with
    database parameters.

    The following PVs currently exist when reading ST_BeamParams:
    - BP:Veto_RBV
    - BP:BeamClassRanges_RBV
    - BP:BeamClass_RBV
    - BP:Cohort_RBV
    - BP:Rate_RBV
    - BP:Transmission_RBV
    - BP:PhotonEnergy_RBV
    - BP:PhotonEnergyRanges_RBV
    - BP:Valid_RBV

    The attribute names here are the database column headers.
    Note that there are not currently any aperature/damage limit/notes PVs.

    We'll also add the best match for name and a "loaded" check.

    For a normal IOC the prefix will be something like:
    IM1L0:XTES:MMS:STATE:
    Which should be systematic to some extent.

    For the test IOC the prefix is:
    PLC:TST:MOT:SIM:XPIM:MMS:STATE:
    """
    loaded = Cpt(
        EpicsSignalRO,
        'PMPS_LOADED_RBV',
        doc='True if the DB has been loaded for this state.',
    )
    lookup = Cpt(
        EpicsSignalRO,
        'PMPS_STATE_RBV',
        string=True,
        doc='Lookup key for this state.',
    )
    nRate = Cpt(
        EpicsSignalRO,
        'BP:Rate_RBV',
        doc='Rate limit with NC beam.',
    )
    nBeamClassRange = Cpt(
        EpicsSignalRO,
        'BP:BeamClassRanges_RBV',
        doc='Acceptable beam parameters with SC Beam.',
    )
    neVRange = Cpt(
        EpicsSignalRO,
        'BP:PhotonEnergyRanges_RBV',
        doc='Acceptable photon energies.',
    )
    nTran = Cpt(
        EpicsSignalRO,
        'BP:Transmission_RBV',
        doc='Gas attenuator transmission limit.',
    )


class AllStateBP(Device):
    """
    All possible beam parameters for a state device.
    """
    state_01 = Cpt(StateBeamParameters, '01:')
    state_02 = Cpt(StateBeamParameters, '02:')
    state_03 = Cpt(StateBeamParameters, '03:')
    state_04 = Cpt(StateBeamParameters, '04:')
    state_05 = Cpt(StateBeamParameters, '05:')
    state_06 = Cpt(StateBeamParameters, '06:')
    state_07 = Cpt(StateBeamParameters, '07:')
    state_08 = Cpt(StateBeamParameters, '08:')
    state_09 = Cpt(StateBeamParameters, '09:')
    state_10 = Cpt(StateBeamParameters, '10:')
    state_11 = Cpt(StateBeamParameters, '11:')
    state_12 = Cpt(StateBeamParameters, '12:')
    state_13 = Cpt(StateBeamParameters, '13:')
    state_14 = Cpt(StateBeamParameters, '14:')
    state_15 = Cpt(StateBeamParameters, '15:')

    def get_table_data(self) -> dict[str, dict[str, Any]]:
        """
        Create a dict that looks like what we get from the database.

        This will be a mapping from lookup key to value mapping.
        """
        data = {}
        for num in range(1, 16):
            state_bp: StateBeamParameters = getattr(self, f'state_{num:02}')
            name = state_bp.lookup.get()
            if name:
                data[name] = {
                    'name': name,
                    'nRate': state_bp.nRate.get(),
                    'nBeamClassRange': clean_bitmask(
                        state_bp.nBeamClassRange.get(), 16,
                    ),
                    'neVRange': clean_bitmask(state_bp.neVRange.get(), 32),
                    'nTran': state_bp.nTran.get(),
                }
        return data


def clean_bitmask(bitmask: int, width: int) -> str:
    """
    Takes the bitmask int from EPICS and makes it a readable string.

    - EPICS unsigned types fix
    - display as string
    - zero pad
    """
    if bitmask < 0:
        bitmask += 2**width
    bitmask = bin(bitmask)[2:]
    while len(bitmask) < width:
        bitmask = '0' + bitmask
    return bitmask
