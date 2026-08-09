# toggl_to_odoo

**toggl_to_odoo** is a tool to synchronize entries from **Timewarrior** to timesheets in an **Odoo** database

## Setup

###### Install

- Clone this repository
- Install dependencies for your python3 environment:
   ```sh
   pip3 install -r requirements.txt
   ```
- Install [Timewarrior](https://timewarrior.net/) (the `timew` binary must be on your `PATH`)

###### Timewarrior side

Timewarrior projects are stored as *tags* of the same name, and the task
description is stored as the interval *annotation*. Using the suggested
converters, entries should be tracked with the relevant `Odoo-*` tag and an
annotation in the format `[odoo task id] title` for tasks filed under
"Odoo-psbe" or "Odoo-maintenance":
```sh
timew start Odoo-psbe
timew annotate '[56012] Fix accounting module'
timew stop
```

Look into [converters/odoo_common.py](converters/odoo_common.py) to get an idea of the other tags you need.  
For example *Misc* entries have to be tagged with "Odoo-misc".

## Guide

### Usage

To run the synchronization, run :
```sh
python3 -m toggl_to_odoo upload toggl2odoo https://www.odoo.com openerp history
```

## Testing

The upload pipeline is tested end-to-end with mocks: the `timew export` output
payload is fed straight into the normal deserialization code, and the Odoo
XML-RPC server is replaced by an in-memory fake. No network or configuration
is required:

```sh
python3 -m unittest discover -t .
```