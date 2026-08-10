import CoreLocation
import Foundation
import HealthKit
import HealthOutboxCore

enum HealthExportError: LocalizedError {
    case unavailable

    var errorDescription: String? {
        "Apple Health data is not available on this device."
    }
}

@MainActor
final class HealthKitExporter: ObservableObject {
    @Published private(set) var status = "Ready"
    @Published private(set) var isBusy = false
    @Published private(set) var lastExportCount = 0

    private let healthStore = HKHealthStore()
    private let folderStore: FolderStore
    private var observerQuery: HKObserverQuery?

    init(folderStore: FolderStore) {
        self.folderStore = folderStore
    }

    func requestAuthorization() async {
        await perform("Apple Health access enabled") {
            try await self.authorize()
            try await self.enableBackgroundDelivery()
        }
    }

    func exportAll() async {
        await export(since: nil)
    }

    func exportRecent(days: Int = 7) async {
        await export(since: Calendar.current.date(byAdding: .day, value: -days, to: Date()))
    }

    func prepareBackgroundUpdates() async {
        guard HKHealthStore.isHealthDataAvailable() else { return }
        do {
            try await enableBackgroundDelivery()
        } catch {
            status = error.localizedDescription
        }
    }

    private func authorize() async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw HealthExportError.unavailable
        }
        try await healthStore.requestAuthorization(toShare: [], read: readTypes())
    }

    private func readTypes() -> Set<HKObjectType> {
        let identifiers: [HKQuantityTypeIdentifier] = [
            .heartRate,
            .distanceWalkingRunning,
            .activeEnergyBurned,
            .runningPower,
            .runningSpeed,
            .runningStrideLength,
            .runningVerticalOscillation,
            .runningGroundContactTime,
        ]
        let quantities = identifiers.compactMap(HKQuantityType.quantityType(forIdentifier:))
        var types = Set<HKObjectType>(quantities.map { $0 })
        types.insert(HKObjectType.workoutType())
        types.insert(HKSeriesType.workoutRoute())
        return types
    }

    private func export(since: Date?) async {
        await perform(nil) {
            try await self.authorize()
            let workouts = try await self.runningWorkouts(since: since)
            var count = 0
            for workout in workouts where self.isAppleOrigin(workout) {
                let payload = try await self.payload(for: workout)
                try self.folderStore.write(payload)
                count += 1
            }
            self.lastExportCount = count
            self.status = "Exported \(count) Apple running workout(s)"
        }
    }

    private func perform(_ success: String?, operation: () async throws -> Void) async {
        isBusy = true
        defer { isBusy = false }
        do {
            try await operation()
            if let success { status = success }
        } catch {
            status = error.localizedDescription
        }
    }

    private func isAppleOrigin(_ workout: HKWorkout) -> Bool {
        let bundle = workout.sourceRevision.source.bundleIdentifier.lowercased()
        let manufacturer = workout.device?.manufacturer?.lowercased() ?? ""
        let model = workout.device?.model?.lowercased() ?? ""
        if bundle.contains("garmin") || manufacturer.contains("garmin") {
            return false
        }
        return bundle.hasPrefix("com.apple.")
            || manufacturer.contains("apple")
            || model.contains("watch")
    }

    private func runningWorkouts(since: Date?) async throws -> [HKWorkout] {
        var predicates: [NSPredicate] = [HKQuery.predicateForWorkouts(with: .running)]
        if let since {
            predicates.append(
                HKQuery.predicateForSamples(
                    withStart: since,
                    end: nil,
                    options: [.strictStartDate]
                )
            )
        }
        let predicate = NSCompoundPredicate(andPredicateWithSubpredicates: predicates)
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: HKObjectType.workoutType(),
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: [
                    NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
                ]
            ) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume(returning: samples as? [HKWorkout] ?? [])
                }
            }
            healthStore.execute(query)
        }
    }

    private func payload(for workout: HKWorkout) async throws -> HealthWorkoutPayload {
        let route = try await routePoints(for: workout)
        let heartRate = try await values(
            .heartRate,
            unit: HKUnit.count().unitDivided(by: .minute()),
            workout: workout
        )
        let rawDistance = try await values(
            .distanceWalkingRunning,
            unit: .meter(),
            workout: workout
        )
        let runningPower = try await values(.runningPower, unit: .watt(), workout: workout)
        let runningSpeed = try await values(
            .runningSpeed,
            unit: HKUnit.meter().unitDivided(by: .second()),
            workout: workout
        )
        let strideLength = try await values(
            .runningStrideLength, unit: .meter(), workout: workout
        )
        let verticalOscillation = try await values(
            .runningVerticalOscillation, unit: .meter(), workout: workout
        )
        let groundContactTime = try await values(
            .runningGroundContactTime, unit: .second(), workout: workout
        )
        let distance = distanceMeters(for: workout)
        var accumulated = 0.0
        let cumulativeDistance = rawDistance.map { sample in
            accumulated += sample.value
            return TimedValue(offsetSeconds: sample.offsetSeconds, value: accumulated)
        }
        let tolerance = max(25, distance * 0.02)
        let safeDistanceSamples = abs((cumulativeDistance.last?.value ?? distance) - distance)
            <= tolerance ? cumulativeDistance : []
        return HealthWorkoutPayload(
            id: workout.uuid,
            name: "Apple Health Run",
            startDate: iso8601(workout.startDate),
            endDate: iso8601(workout.endDate),
            durationSeconds: workout.duration,
            distanceMeters: distance,
            calories: calories(for: workout),
            timezoneOffsetSeconds: TimeZone.current.secondsFromGMT(for: workout.startDate),
            deviceName: deviceName(for: workout),
            sourceBundleIdentifier: workout.sourceRevision.source.bundleIdentifier,
            route: route,
            samples: Samples(
                heartRate: heartRate,
                distance: safeDistanceSamples,
                runningPower: runningPower,
                runningSpeed: runningSpeed,
                strideLength: strideLength,
                verticalOscillation: verticalOscillation,
                groundContactTime: groundContactTime
            )
        )
    }

    private func values(
        _ identifier: HKQuantityTypeIdentifier,
        unit: HKUnit,
        workout: HKWorkout
    ) async throws -> [TimedValue] {
        guard let type = HKQuantityType.quantityType(forIdentifier: identifier) else { return [] }
        let predicate = HKQuery.predicateForObjects(from: workout)
        let samples: [HKQuantitySample] = try await withCheckedThrowingContinuation {
            continuation in
            let query = HKSampleQuery(
                sampleType: type,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: [
                    NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: true)
                ]
            ) { _, results, error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume(returning: results as? [HKQuantitySample] ?? [])
                }
            }
            healthStore.execute(query)
        }
        return samples.map {
            TimedValue(
                offsetSeconds: max(0, $0.endDate.timeIntervalSince(workout.startDate)),
                value: $0.quantity.doubleValue(for: unit)
            )
        }
    }

    private func routePoints(for workout: HKWorkout) async throws -> [RoutePoint] {
        let predicate = HKQuery.predicateForObjects(from: workout)
        let routes: [HKWorkoutRoute] = try await withCheckedThrowingContinuation {
            continuation in
            let query = HKSampleQuery(
                sampleType: HKSeriesType.workoutRoute(),
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: nil
            ) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume(returning: samples as? [HKWorkoutRoute] ?? [])
                }
            }
            healthStore.execute(query)
        }
        var locations: [CLLocation] = []
        for route in routes {
            locations += try await locations(for: route)
        }
        return locations.sorted(by: { $0.timestamp < $1.timestamp }).map {
            RoutePoint(
                offsetSeconds: max(0, $0.timestamp.timeIntervalSince(workout.startDate)),
                latitude: $0.coordinate.latitude,
                longitude: $0.coordinate.longitude,
                altitudeMeters: $0.verticalAccuracy >= 0 ? $0.altitude : nil,
                speedMetersPerSecond: $0.speed >= 0 ? $0.speed : nil
            )
        }
    }

    private func locations(for route: HKWorkoutRoute) async throws -> [CLLocation] {
        try await withCheckedThrowingContinuation { continuation in
            var all: [CLLocation] = []
            let query = HKWorkoutRouteQuery(route: route) { _, locations, done, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                all += locations ?? []
                if done { continuation.resume(returning: all) }
            }
            healthStore.execute(query)
        }
    }

    private func distanceMeters(for workout: HKWorkout) -> Double {
        guard let type = HKQuantityType.quantityType(forIdentifier: .distanceWalkingRunning) else {
            return 0
        }
        return workout.statistics(for: type)?.sumQuantity()?.doubleValue(for: .meter()) ?? 0
    }

    private func calories(for workout: HKWorkout) -> Double? {
        guard let type = HKQuantityType.quantityType(forIdentifier: .activeEnergyBurned) else {
            return nil
        }
        return workout.statistics(for: type)?.sumQuantity()?.doubleValue(for: .kilocalorie())
    }

    private func deviceName(for workout: HKWorkout) -> String? {
        guard let device = workout.device else { return nil }
        return [device.manufacturer, device.model, device.name]
            .compactMap { $0 }
            .joined(separator: " ")
    }

    private func iso8601(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.string(from: date)
    }

    private func enableBackgroundDelivery() async throws {
        let workoutType = HKObjectType.workoutType()
        try await withCheckedThrowingContinuation { continuation in
            healthStore.enableBackgroundDelivery(for: workoutType, frequency: .immediate) {
                success, error in
                if let error {
                    continuation.resume(throwing: error)
                } else if success {
                    continuation.resume(returning: ())
                } else {
                    continuation.resume(throwing: HealthExportError.unavailable)
                }
            }
        }
        guard observerQuery == nil else { return }
        let query = HKObserverQuery(sampleType: workoutType, predicate: nil) {
            [weak self] _, completion, error in
            guard error == nil else {
                completion()
                return
            }
            Task { @MainActor [weak self] in
                await self?.exportRecent(days: 2)
                completion()
            }
        }
        observerQuery = query
        healthStore.execute(query)
    }
}
