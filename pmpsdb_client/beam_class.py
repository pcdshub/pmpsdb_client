"""
Module to define beam class helpers.

This includes:
- The BeamClass dataclass
- beamclasses, a list of available beam classes in order
- summarize_beam_class_bitmask, a function that returns a str table that
  explains the impact of a specific beam class bitmask.
"""
import dataclasses
from typing import Optional, Union, get_args, get_origin

from prettytable import PrettyTable


@dataclasses.dataclass(frozen=True)
class BeamClass:
    """
    Dataclass that represents one beam class.

    This is a set of limiting parameters on the LCLS2 accelerator.
    Any omitted parameter means that there is no limit.

    The functional parameters are:
    - charge_time
    - pulse_period
    - charge

    All other parameters are metadata to help understand the impact
    of those three parameters.
    """
    index: int
    name: str
    charge_time: Optional[float]
    pulse_period: Optional[float]
    charge: Optional[int]
    rate_max: Optional[int]
    current: Optional[float]
    power: Optional[float]
    int_energy: Optional[float]
    notes: Optional[str]

    @classmethod
    def from_strs(cls, *args):
        """
        Load a beamclass from a list of strings that match the fields.
        """
        # Coerce the types
        new_args = []
        for value, field in zip(args, dataclasses.fields(cls)):
            origin = get_origin(field.type)
            # Normal types
            if origin is None:
                new_args.append(field.type(value))
            # Optional
            elif origin is Union:
                if value is None:
                    new_args.append(None)
                else:
                    the_type = get_args(field.type)[0]
                    new_args.append(the_type(value))
            else:
                raise NotImplementedError(
                    'You added to this class without thinking about this function!'
                )
        return cls(*new_args)


# Copied from https://confluence.slac.stanford.edu/pages/viewpage.action?pageId=341246543 and tweaked
header = """
Index	Display Name	∆T (s)	dt (s)	Q (pC)	Rate max (Hz)	Current (nA)	Power @ 4 GeV (W)	Int. Energy @ 4 GeV (J)	Notes
""".strip().split('\t')
table = """
0	Beam Off	0.5	-	0	0	0	0	0	Beam off, Kickers off
1	Kicker STBY	0.5	-	0	0	0	0	0	Beam off, Kickers standby
2	BC1Hz	1	1	350	1	0.35	1.4	1.4	350 pC x 1 Hz
3	BC10Hz	1	0.1	3500	10	3.5	14	14	350 pC X 10 Hz
4	Diagnostic	0.5	-	5000	-	10	40	20	50 pC x 200 Hz
5	BC120Hz	0.2	0.0083	6000	120	30	120	24	250 pC x 120 Hz
6	Tuning	0.2	-	7000	-	35	140	28	100 pC X 350 Hz
7	1% MAP	0.01	-	3000	-	300	1200	12	100 pC X 3 kHz
8	5% MAP	0.003	-	4500	-	1500	6000	18	100 pC x 15 kHz
9	10% MAP	0.001	-	3000	-	3000	12000	12	100 pC X 30 kHz
10	25% MAP	4e-4	-	3000	-	7500	30000	12	100 pC x 75 kHz
11	50% MAP	2e-1	-	3000	-	15000	60000	12	100 pC x 150 kHz
12	100% MAP	2e-4	-	6000	-	30000	120000	24	100 pC x 300 kHz
13	Unlimited	-	-	-	-	-	-	-	-
14	Spare	-	-	-	-	-	-	-	-
15	Spare	-	-	-	-	-	-	-	-
"""

beam_classes: list[BeamClass] = []

for line in table.split('\n'):
    if not line:
        continue
    entries = line.split('\t')
    for i, entry in enumerate(entries):
        if entry == '-':
            entries[i] = None
    beam_classes.append(BeamClass.from_strs(*entries))


def summarize_beam_class_bitmask(bitmask: int) -> str:
    """
    Creates a nice table summarizing what the bitmask means.

    The bitmask is used by the pmps system to determine which beam
    classes are permissable for a specific device state.
    """
    table = PrettyTable()
    table.field_names = ['OK'] + header
    data_attrs = [field.name for field in dataclasses.fields(BeamClass)]

    def add_row(ok: bool, beam_class: BeamClass) -> None:
        if ok:
            row_data = ['Yes']
        else:
            row_data = ['No']
        for attr in data_attrs:
            value = getattr(beam_class, attr)
            if value is None:
                value = '-'
            row_data.append(value)
        table.add_row(row_data)

    # First row is no beam, which is always ok
    add_row(ok=True, beam_class=beam_classes[0])
    # The rest of the rows check the bitmask
    for beam_class in beam_classes[1:]:
        add_row(ok=bitmask & 1, beam_class=beam_class)
        bitmask = bitmask >> 1

    return table.get_string()
