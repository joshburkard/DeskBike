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

## Prerequisites

you need a bluetooth proxy. i can recommend the [ESP32 - M5 Atom lite](https://shop.m5stack.com/products/atom-lite-esp32-development-kit?ref=NabuCasa), which you can configure and attach to Home Assistant on this [page](https://esphome.io/projects/?type=bluetooth).

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

# Dashboard

you can create a dashboard like this:

```
      - type: custom:canvas-gauge-card
        entity: sensor.deskbike_xxxxx_current_speed
        card_height: 250
        background_color: '#FFF'
        majorTicksDec: 1
        gauge:
          type: radial-gauge
          title: km/h
          width: 250
          height: 250
          exactTicks: true
          borderShadowWidth: 5
          borderOuterWidth: 0
          borderMiddleWidth: 0
          borderInnerWidth: 0
          minValue: 0
          maxValue: 40
          startAngle: 45
          ticksAngle: 270
          valueBox: true
          valueInt: 1
          valueDec: 1
          majorTicks:
            - 8
            - 16
            - 24
            - 32
          minorTicks: 1
          strokeTicks: true
          borders: false
          highlights:
            - from: 0
              to: 8
              color: '#47DF43'
            - from: 8
              to: 16
              color: '#94fe92'
            - from: 16
              to: 24
              color: '#eee780'
            - from: 24
              to: 32
              color: '#F28A5C'
            - from: 32
              to: 40
              color: '#db4437'
        needle: true
      - type: entities
        entities:
          - entity: sensor.deskbike_xxxxx_daily_distance
            name: Daily Distance
          - entity: sensor.deskbike_xxxxx_daily_active_time
            name: Daily Active Time
          - entity: sensor.deskbike_xxxxx_daily_crank_revolutions
            name: Daily Crank Revolutions
          - entity: sensor.deskbike_xxxxx_total_distance
            name: Total Distance
          - entity: sensor.deskbike_xxxxx_total_active_time
            name: Total Active Time
          - entity: sensor.deskbike_xxxxx_total_crank_revolutions
            name: Total Crank Revolutions
          - entity: sensor.deskbike_xxxxx_battery
            name: Battery

```