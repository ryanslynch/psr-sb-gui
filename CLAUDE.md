# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Description

We are building a wizard-style GUI for astronomers using the Green
Bank Telescope (GBT) to observe pulsars.  It can be difficult to learn
how to use the GBT.  The GUI will make it easier by allowing
astronomers to provide information about the sources they want to
observe and the scientific purpose of their observations.  The GUI
will then use this information to fill in the GBT-specific technical
information, producing scheduling blocks that will be executed using
the Astrid observing interface.  We'll use PyQt and PySide6 to build
the GUI.

## Observer Workflow

The workflow for observers that are using the GUI will be as follows

1. Specify the name, coordinates, and observing scan length of one or
   more astronomical sources.  Coordinates may be specified in the
   J2000, B1950, or Galactic coordinate system.
2. Select the radio frequency range and observing mode.  Users should
   have the option of specify different frequency ranges and observing
   modes for each source, or applying the same frequency range and
   observing mode for all sources.  Users can also choose whether or
   not to include a polarization calibration observation.
3. Choose whether to include a flux calibration observation.  If users
   are select multiple different observing modes a flux calibration
   scan will need to be performed in each mode.
4. Review the default values of the observe-mode-specific parameters
   and make changes if needed.  We expect that only experts will make
   changes.
5. Generate a draft Astrid schedule block and make changes if
   necessary.  We expect that only experts will make changes.
6. Save the final scheduling block.

## Development Approach

We will build the GUI incrementally.  We'll start by developing the
basic framework and workflow.  Then we'll add all the necessary menus,
entry fields, and detailed functionality.  Then we'll make sure that
it handles any special cases and produces valid scheduling blocks.  We
will need to make sure that dependencies between certain observing
parameters are properly handled, and that default values follow
best-practices and recommended observing procedures.  Since this will
be a complex, multi-step process **use planning mode**.

## Reference Documentation

Before beginning, please read the following documentation to
familiarize yourself with Astrid scheduling blocks and with the VEGAS
Pulsar Mode backend.

- [Astrid Overview](https://gbtdocs.readthedocs.io/en/latest/references/astrid.html)
- [Scheduling Blocks Overview](https://gbtdocs.readthedocs.io/en/latest/references/scheduling-blocks.html)
- [Scheduling Block Commands](https://gbtdocs.readthedocs.io/en/latest/references/observing/sb_commands.html)
- [Catalogs](https://gbtdocs.readthedocs.io/en/latest/references/observing/catalog.html)
- [Configuration Keywords](https://gbtdocs.readthedocs.io/en/latest/references/observing/configure.html)
- [The VEGAS Pulsar Mode Backend](https://gbtdocs.readthedocs.io/en/latest/references/backends/vpm.html)
- [An Example Pulsar Timing Observation](https://gbtdocs.readthedocs.io/en/latest/how-tos/observing_modes/pulsars/pulsar_time_obs.html)
- [An Example Pulsar Searching Observation](https://gbtdocs.readthedocs.io/en/latest/how-tos/observing_modes/pulsars/pulsar_search.html)
- [An Example Flux Calibration Observation](https://gbtdocs.readthedocs.io/en/latest/how-tos/observing_modes/pulsars/pulsar_flux_cal.html)

It's possible that some of this reference material is out of date or
incorrect, so if anything seems inconsistent or doesn't make sense,
please ask me for clarification.
