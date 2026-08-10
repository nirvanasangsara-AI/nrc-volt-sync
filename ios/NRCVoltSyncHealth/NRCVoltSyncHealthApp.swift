import SwiftUI

@main
struct NRCVoltSyncHealthApp: App {
    @StateObject private var folderStore: FolderStore
    @StateObject private var exporter: HealthKitExporter

    init() {
        let folders = FolderStore()
        _folderStore = StateObject(wrappedValue: folders)
        _exporter = StateObject(wrappedValue: HealthKitExporter(folderStore: folders))
    }

    var body: some Scene {
        WindowGroup {
            ContentView(folderStore: folderStore, exporter: exporter)
                .task { await exporter.prepareBackgroundUpdates() }
        }
    }
}
