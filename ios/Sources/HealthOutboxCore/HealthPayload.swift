import Foundation

public struct HealthWorkoutPayload: Codable, Equatable, Sendable {
    public static let currentSchema = "io.github.nrcvoltsync.healthkit.workout"
    public static let currentSchemaVersion = 1

    public let schema: String
    public let schemaVersion: Int
    public let id: UUID
    public let activityType: String
    public let name: String
    public let startDate: String
    public let endDate: String
    public let durationSeconds: Double
    public let distanceMeters: Double
    public let calories: Double?
    public let timezoneOffsetSeconds: Int
    public let deviceName: String?
    public let sourceBundleIdentifier: String?
    public let route: [RoutePoint]
    public let samples: Samples

    public init(
        id: UUID,
        name: String,
        startDate: String,
        endDate: String,
        durationSeconds: Double,
        distanceMeters: Double,
        calories: Double?,
        timezoneOffsetSeconds: Int,
        deviceName: String?,
        sourceBundleIdentifier: String?,
        route: [RoutePoint],
        samples: Samples
    ) {
        schema = Self.currentSchema
        schemaVersion = Self.currentSchemaVersion
        self.id = id
        activityType = "running"
        self.name = name
        self.startDate = startDate
        self.endDate = endDate
        self.durationSeconds = durationSeconds
        self.distanceMeters = distanceMeters
        self.calories = calories
        self.timezoneOffsetSeconds = timezoneOffsetSeconds
        self.deviceName = deviceName
        self.sourceBundleIdentifier = sourceBundleIdentifier
        self.route = route
        self.samples = samples
    }

    enum CodingKeys: String, CodingKey {
        case schema
        case schemaVersion = "schema_version"
        case id
        case activityType = "activity_type"
        case name
        case startDate = "start_date"
        case endDate = "end_date"
        case durationSeconds = "duration_s"
        case distanceMeters = "distance_m"
        case calories
        case timezoneOffsetSeconds = "timezone_offset_s"
        case deviceName = "device_name"
        case sourceBundleIdentifier = "source_bundle_id"
        case route
        case samples
    }
}

public struct RoutePoint: Codable, Equatable, Sendable {
    public let offsetSeconds: Double
    public let latitude: Double
    public let longitude: Double
    public let altitudeMeters: Double?
    public let speedMetersPerSecond: Double?

    public init(
        offsetSeconds: Double,
        latitude: Double,
        longitude: Double,
        altitudeMeters: Double?,
        speedMetersPerSecond: Double?
    ) {
        self.offsetSeconds = offsetSeconds
        self.latitude = latitude
        self.longitude = longitude
        self.altitudeMeters = altitudeMeters
        self.speedMetersPerSecond = speedMetersPerSecond
    }

    enum CodingKeys: String, CodingKey {
        case offsetSeconds = "offset_s"
        case latitude
        case longitude
        case altitudeMeters = "altitude_m"
        case speedMetersPerSecond = "speed_m_s"
    }
}

public struct TimedValue: Codable, Equatable, Sendable {
    public let offsetSeconds: Double
    public let value: Double

    public init(offsetSeconds: Double, value: Double) {
        self.offsetSeconds = offsetSeconds
        self.value = value
    }

    enum CodingKeys: String, CodingKey {
        case offsetSeconds = "offset_s"
        case value
    }
}

public struct Samples: Codable, Equatable, Sendable {
    public let heartRate: [TimedValue]
    public let distance: [TimedValue]
    public let runningPower: [TimedValue]
    public let runningSpeed: [TimedValue]
    public let strideLength: [TimedValue]
    public let verticalOscillation: [TimedValue]
    public let groundContactTime: [TimedValue]

    public init(
        heartRate: [TimedValue] = [],
        distance: [TimedValue] = [],
        runningPower: [TimedValue] = [],
        runningSpeed: [TimedValue] = [],
        strideLength: [TimedValue] = [],
        verticalOscillation: [TimedValue] = [],
        groundContactTime: [TimedValue] = []
    ) {
        self.heartRate = heartRate
        self.distance = distance
        self.runningPower = runningPower
        self.runningSpeed = runningSpeed
        self.strideLength = strideLength
        self.verticalOscillation = verticalOscillation
        self.groundContactTime = groundContactTime
    }

    enum CodingKeys: String, CodingKey {
        case heartRate = "heart_rate"
        case distance
        case runningPower = "running_power"
        case runningSpeed = "running_speed"
        case strideLength = "stride_length"
        case verticalOscillation = "vertical_oscillation"
        case groundContactTime = "ground_contact_time"
    }
}

public enum PayloadEncoder {
    public static func encode(_ payload: HealthWorkoutPayload) throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return try encoder.encode(payload)
    }
}
