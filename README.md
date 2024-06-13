# DeskBike

this is a custom integration for [Home Assistant](https://www.home-assistant.io/) to connect to a [DeskBike](https://deskbike.nl/)

with this integration, you can connect from Home Assistant to the Desk Bike and get this values:

- Speed
- Battery
- Daily / Total
  - Crank Revolutions
  - Active Time
  - Distance

this integration is currently in beta state and i expect issues.

## Installation

create a new folder `deskbike` below `/config/custom_components` and copy all files to that folder or its subfolder.

restart Home Assistant

go to `Settings` --> `Devices & Services`

click on `Add Integration` and select `Deskbike`.

now your Deskbike should be nearby and you should be active on it, otherwise it will not be detected.

the Deskbike will be detected and added. you will see it like follow:

![](/doc/example-01.png)

![](/doc/example-02.png)

![](/doc/example-03.png)

now you can create a custom dashboard from its sensors:

![](/doc/example-04.png)

## open tasks

- optimization of sensors
  - units

as i'm a python newbie, any support and help will be appreciated.
