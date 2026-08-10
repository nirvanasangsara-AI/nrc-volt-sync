# Third-party notices

The MIT License in this repository applies to NRC Volt Sync's own source code. Dependencies are
installed by the package manager and remain governed by their own licenses.

## Direct runtime dependencies

- [`python-garminconnect`](https://github.com/cyberjunky/python-garminconnect), currently resolved
  to 0.3.9, is MIT-licensed. Copyright 2020-2026 Ron Klinkien and contributors. NRC Volt Sync uses
  it for the runner's Garmin authentication, duplicate lookup, and FIT upload.
- [`Garmin FIT Python SDK`](https://developer.garmin.com/fit/download/), currently resolved to
  21.212.0, is governed by Garmin's
  [FIT Protocol License](https://developer.garmin.com/fit/protocol/). Its terms are separate from
  NRC Volt Sync's MIT License. NRC Volt Sync uses it to encode and validate interoperable FIT files.
- [`HTTPX`](https://github.com/encode/httpx), currently resolved to 0.28.1, is BSD-3-Clause
  licensed. NRC Volt Sync uses it for Strava OAuth and API requests.

No source code from these projects is vendored into this repository. See `uv.lock` for the complete
resolved dependency graph and the linked upstream projects for authoritative license texts.

## Development tooling

- [`XcodeGen`](https://github.com/yonaskolb/XcodeGen) is MIT-licensed. It generates the checked-in
  iOS Xcode project from `ios/project.yml` and is used by CI to verify that the project is current.
  XcodeGen is a build-time tool and is not shipped inside the app.
