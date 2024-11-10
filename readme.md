# DeskBike

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Adds DeskBike support to Home assistant. This integration requires [HACS](https://hacs.xyz).

## Features

this custom component creates:

- A Device in Home Assistant for a DeskBike with:
  - this sensors:
    - Cadence
    - Daily Active Time
    - Daily Calories Burned
    - Daily Distance
    - Is Active
    - Speed
    - Total Active Time
    - Total Calories Burned
    - Total Distance
  - Configurations:
    - Cyclist Weight kg
  - Diagnostics:
    - Battery
    - Firmware Version
    - Hardware Version
    - Is Connected
    - Last Active
    - Model Number
    - Seriual Number
    - Software Version

## Setup

Recommended to be installed via [HACS](https://github.com/hacs/integration)

1. Go to HACS -> Integrations
2. Add this [repo](https://github.com/joshburkard/DeskBike) to your HACS custom repositories (https://hacs.xyz/docs/faq/custom_repositories)
3. Search for DeskBike and install.
4. Restart Home Assistant
5. if you start using your DeskBike, it should be automatically detected
6. add it to Home Assistant

## Notes

This custom component was created without any knowledge of Python but with use of Claude AI
