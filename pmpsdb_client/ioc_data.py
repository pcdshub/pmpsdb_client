"""
Module to define the EPICS interface to live PLC statuses.

This contains ophyd device definitions that will be useful
for checking the status or asking for a refresh.

In the future this may be reworked to use PyDM channels.
"""
import logging
from typing import Any

from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal, EpicsSignalRO

logger = logging.getLogger(__name__)


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


class ApertureSize(Device):
    """
    A subelement of ST_BeamParams that represents one ST_PMPS_Aperture.

    OK_RBV is omitted because it is not used for beam parameter sets.
    It is a communication field for live data from the Arbiter.
    """
    width = Cpt(
        EpicsSignalRO,
        'Width_RBV',
        doc='The horizontal aperture opening size.',
    )
    height = Cpt(
        EpicsSignalRO,
        'Height_RBV',
        doc='The vertical aperture opening size.',
    )


class BeamParameters(Device):
    """
    A set of beam parameters as sent to the arbiter.

    This represents the elements from ST_BeamParams that match up with
    database parameters. Elements that are used only for Arbiter readbacks
    are omitted.

    The attribute names here are the database column headers where applicable.

    The following PVs/subelements are included:
    - Rate_RBV
    - BeamClassRanges_RBV
    - PhotonEnergyRanges_RBV
    - Transmission_RBV
    - Apertures:01, 02, 03, 04
    """
    nRate = Cpt(
        EpicsSignalRO,
        'Rate_RBV',
        doc='Rate limit with NC beam.',
    )
    nBeamClassRange = Cpt(
        EpicsSignalRO,
        'BeamClassRanges_RBV',
        doc='Acceptable beam parameters with SC Beam.',
    )
    neVRange = Cpt(
        EpicsSignalRO,
        'eVRanges_RBV',
        doc='Acceptable photon energies.',
    )
    nTran = Cpt(
        EpicsSignalRO,
        'Transmission_RBV',
        doc='Gas attenuator transmission limit.',
    )
    aperture1 = Cpt(
        ApertureSize,
        'Apt:01:',
        doc='Opening setting of aperture 1',
    )
    aperture2 = Cpt(
        ApertureSize,
        'Apt:02:',
        doc='Opening setting of aperture 2',
    )
    aperture3 = Cpt(
        ApertureSize,
        'Apt:03:',
        doc='Opening setting of aperture 3',
    )
    aperture4 = Cpt(
        ApertureSize,
        'Apt:04:',
        doc='Opening setting of aperture 4',
    )

    def get_table_data(self) -> dict[str, Any]:
        """
        Return a mapping from table key to value.

        This is similar to self.get() but with some cleanup applied
        to the bitmasks to change them from int to str.
        """
        return {
            'nRate': self.nRate.get(),
            'nBeamClassRange': clean_bitmask(self.nBeamClassRange.get(), 15),
            'neVRange': clean_bitmask(self.neVRange.get(), 32),
            'nTran': self.nTran.get(),
            'aperture1_width': self.aperture1.width.get(),
            'aperture1_height': self.aperture1.height.get(),
            'aperture2_width': self.aperture2.width.get(),
            'aperture2_height': self.aperture2.height.get(),
            'aperture3_width': self.aperture3.width.get(),
            'aperture3_height': self.aperture3.height.get(),
            'aperture4_width': self.aperture4.width.get(),
            'aperture4_height': self.aperture4.height.get(),
        }


class DatabaseBeamParameters(Device):
    """
    The beam parameters database struct, ST_DbStateParams.

    This includes the database parameters and some auxiliary fields from the database load.
    The attribute names here are the database column headers where applicable/possible.
    """
    loaded = Cpt(
        EpicsSignalRO,
        'PMPS_LOADED_RBV',
        doc='True if the DB has been loaded for this state.',
    )
    db_name = Cpt(
        EpicsSignalRO,
        'PMPS_STATE_RBV',
        string=True,
        doc='Lookup key for this state.',
    )
    db_id = Cpt(
        EpicsSignalRO,
        'PMPS_ID_RBV',
        doc='Database and assertion id for this state.',
    )
    beam_parameters = Cpt(
        BeamParameters,
        'BP:',
        doc='The beam parameter set as sent to the arbiter PLC.',
    )

    def get_table_data(self) -> dict[str, Any]:
        """
        Return a mapping from table key to value.
        """
        data = {
            'loaded': 'True' if self.loaded.get() else 'False',
            'db_name': self.db_name.get(),
            'db_id': self.db_id.get(),
        }
        data.update(self.beam_parameters.get_table_data())
        return data


class StateBeamParameters(Device):
    """
    One state position, which includes position settings and beam parameters.

    The attribute names here are the database column headers where applicable/possible.

    For a normal IOC the prefix will be something like:
    IM1L0:XTES:MMS:STATE:01:
    Which should be systematic to some extent.

    For the test IOC the prefix is:
    PLC:TST:MOT:SIM:XPIM:MMS:STATE:
    """
    ctrl_name = Cpt(
        EpicsSignalRO,
        'NAME_RBV',
        string=True,
        doc='The short name you select in a control gui.',
    )
    ctrl_setpoint = Cpt(
        EpicsSignalRO,
        'SETPOINT_RBV',
        doc='The physical position in a control gui.',
    )
    database = Cpt(
        DatabaseBeamParameters,
        '',
        doc='The database entry associated with this device.'
    )

    def get_table_data(self) -> dict[str, Any]:
        """
        Return a mapping from table key to value.
        """
        data = {
            'ctrl_name': self.ctrl_name.get(),
            'ctrl_setpoint': self.ctrl_setpoint.get(),
        }
        data.update(self.database.get_table_data())
        return data


class AllStateBP(Device):
    """
    All possible beam parameters for a state device.

    For a normal IOC the prefix will be something like:
    IM1L0:XTES:MMS:STATE:
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
    transition = Cpt(DatabaseBeamParameters, 'PMPS:TRANS:')

    def get_table_data(self) -> dict[str, dict[str, Any]]:
        """
        Create a dict that looks like what we get from the database.

        This will be a mapping from lookup key to value mapping.
        """
        data = {}
        for num in range(1, 16):
            state_bp: StateBeamParameters = getattr(self, f'state_{num:02}')
            try:
                state_data = state_bp.get_table_data()
            except Exception:
                # Some connection error, probably
                logger.debug('Error getting state parameters', exc_info=True)
                logger.debug('Skip all subsequent states (to avoid timeout chain)')
                break
            database_name = state_data['db_name']
            control_name = state_data['ctrl_name']

            if database_name or (control_name and control_name != 'Invalid'):
                data[database_name] = state_data
            else:
                logger.debug(
                    'State %d had no name (pvs: %s, %s)',
                    num,
                    state_bp.database.db_name.pvname,
                    state_bp.ctrl_name.pvname,
                )
        trans_data = self.transition.get_table_data()
        data[trans_data['db_name']] = trans_data
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
