# Using NRC Volt Sync without an existing Strava account

NRC Volt Sync 0.2 uses Strava as its automatic Apple Workout source. A runner who does not already
use Strava still has two free paths today, but only one is automatic. A completely Strava-free,
full-fidelity automatic path requires an iPhone companion because Apple does not allow macOS apps to
read the HealthKit store.

## Choose a path

| Goal | Free | Automatic | GPS | Heart rate and cadence | Available now |
| --- | --- | --- | --- | --- | --- |
| Use a private Strava account only as a relay | Yes | Yes | Preserved when Strava exposes it | Preserved only when Strava exposes it | Yes |
| Never create a Strava account; recover outdoor history | Yes | No | Preserved when Apple's export contains a timed route | Usually incomplete in GPX; indoor runs have no route | Yes, manual fallback |
| Never use Strava; automatic full-fidelity sync | Intended to be free | Yes | Intended to preserve source data | Intended to preserve source data | Not yet; tracked in [issue 2](https://github.com/nirvanasangsara-AI/nrc-volt-sync/issues/2) |

## Path 1: free private Strava relay

This is the recommended current path for someone who does not otherwise use Strava. A free account
can be used only as a transport layer; NRC Volt Sync has no requirement to post socially, follow
people, or buy a subscription.

1. Create a free Strava account and set the default activity visibility to your preferred private
   setting.
2. In the Strava iPhone app, open **Settings → Manage Apps and Devices → Health**.
3. Connect Health, allow **Workouts** and **Workout Routes**, and enable **Automatic Uploads**.
4. Complete [SETUP.md](SETUP.md) to connect that account to NRC Volt Sync.

Strava officially documents that native Apple Workout activities from the previous 30 days can be
uploaded and that Automatic Uploads handles new eligible workouts. Running cadence is not currently
exposed for every Apple Health run, so NRC Volt Sync cannot restore a field that the source does not
provide.

Official reference: [Apple Health and Strava](https://support.strava.com/en-us/articles/15402024-apple-health-and-strava).

Connecting Strava directly inside NRC does not solve this direction. The Nike–Strava integration
pushes newly recorded Nike activities to Strava; it does not pull Apple Watch or other activities
from Strava into NRC.

Official reference: [Nike and Strava](https://support.strava.com/en-us/articles/15401850-nike-and-strava).

## Path 2: no Strava account, manual Apple Health export

This is a free historical fallback for outdoor runs. It is not the unattended workflow promised by
the automatic service.

1. On iPhone, open **Health → Summary → profile picture or initials → Export All Health Data**.
2. Save the archive to the user's own Mac using Files, AirDrop, or another private method.
3. Keep the archive private. It can contain the user's complete health history, not only runs.
4. After extraction, inspect the workout-route folder for the outdoor run's time-stamped GPX file.
5. Connect Garmin inside NRC before importing the activity.
6. In Garmin Connect Web, choose the upload icon → **Import Data**, then import the matching GPX.
7. If necessary, edit the Garmin activity type to **Running**, then check whether the new activity
   reaches NRC.

Apple officially supports exporting all health and fitness data in XML. Outdoor workout-route GPX
files may also be present in the export archive. Garmin officially accepts FIT, time-stamped GPX,
and TCX activity files. A GPX without timestamps cannot be imported as an activity.

- Apple: [Export all health data](https://support.apple.com/guide/iphone/share-health-and-fitness-data-iph5ede58c3d/ios)
- Garmin: [Manually upload activities](https://support.garmin.com/en-CA/?faq=Ht3ZP52Kju075uKvqTqu99)

### Fidelity limits of the manual export

- Outdoor GPS and timestamps can survive when the route GPX is present.
- GPX commonly lacks the workout's complete heart-rate, cadence, power, and running-dynamics series.
- Indoor runs do not have a GPS route and therefore need a FIT or TCX built from HealthKit samples.
- Matching separate XML sensor records back to one workout can be ambiguous. This project will not
  guess or fabricate missing samples.
- Delivery from a manually imported Garmin activity to NRC is controlled by the Garmin–Nike partner
  connection and is not guaranteed by Garmin's file-import documentation. Test one run first.

The current CLI does not read the Apple export archive. Do not place an export ZIP, XML, GPX, FIT,
or other health file inside the Git repository.

## Uploading to other services

NRC Volt Sync currently automates one destination: Garmin Connect, followed by the user's Garmin–Nike
partner connection. Validated FIT activities produced by the current Strava path remain in the
private local runtime folder. A user may copy an individual FIT to another private location and
manually import it into a service that officially accepts FIT activities.

Do not upload the whole runtime folder or publish a FIT file: it can contain timestamps, GPS routes,
heart rate, and other health data. Automatic multi-service delivery is not generic. Every destination
needs its own documented API, scopes, duplicate rules, and explicit user authorization.

## Why the Mac cannot make the Strava-free path automatic by itself

Apple's HealthKit framework exists on macOS, but Apple documents that macOS apps cannot read or
write HealthKit data and `isHealthDataAvailable()` returns false. Full route and sensor access must
happen on the iPhone after the user grants HealthKit permissions.

Official references:

- [HealthKit availability](https://developer.apple.com/documentation/healthkit/hkhealthstore/ishealthdataavailable())
- [Workout route data](https://developer.apple.com/documentation/healthkit/hkworkoutroute)
- [HealthKit authorization](https://developer.apple.com/documentation/healthkit/authorizing-access-to-health-data)

The planned architecture in [issue 2](https://github.com/nirvanasangsara-AI/nrc-volt-sync/issues/2)
is:

```text
Apple Watch Workout → HealthKit on iPhone → local companion/outbox
→ NRC Volt Sync on Mac → portable FIT → Garmin Connect → Nike Run Club
```

The portable FIT outbox is also the foundation for user-directed imports into other services. Each
automatic destination still needs its own supported API and explicit account authorization; this
project will not scrape services or collect users' credentials on a maintainer server.
