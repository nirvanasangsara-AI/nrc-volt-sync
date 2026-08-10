import Foundation
import XCTest
@testable import HealthOutboxCore

final class HealthPayloadTests: XCTestCase {
    func testPayloadUsesStablePublicSchema() throws {
        let payload = HealthWorkoutPayload(
            id: UUID(uuidString: "11111111-2222-4333-8444-555555555555")!,
            name: "Synthetic Run",
            startDate: "2024-01-01T00:00:00Z",
            endDate: "2024-01-01T00:10:00Z",
            durationSeconds: 590,
            distanceMeters: 1_500,
            calories: 100,
            timezoneOffsetSeconds: 32_400,
            deviceName: "Synthetic Watch",
            sourceBundleIdentifier: "com.example.synthetic",
            route: [
                RoutePoint(
                    offsetSeconds: 0,
                    latitude: 10,
                    longitude: 20,
                    altitudeMeters: -2,
                    speedMetersPerSecond: nil
                )
            ],
            samples: Samples(heartRate: [TimedValue(offsetSeconds: 1.5, value: 140)])
        )

        let data = try PayloadEncoder.encode(payload)
        let object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: data) as? [String: Any]
        )

        XCTAssertEqual(object["schema"] as? String, HealthWorkoutPayload.currentSchema)
        XCTAssertEqual(object["schema_version"] as? Int, 1)
        XCTAssertEqual(object["activity_type"] as? String, "running")
        XCTAssertEqual(object["distance_m"] as? Double, 1_500)
        XCTAssertTrue(String(decoding: data, as: UTF8.self).contains("heart_rate"))
        XCTAssertFalse(String(decoding: data, as: UTF8.self).contains("cadence"))
    }
}
