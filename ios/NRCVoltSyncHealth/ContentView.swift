import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @ObservedObject var folderStore: FolderStore
    @ObservedObject var exporter: HealthKitExporter
    @State private var choosingFolder = false
    @State private var folderError: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Private, no-Strava bridge") {
                    Text(
                        "Exports Apple Watch running workouts from Apple Health to a Files "
                            + "folder you choose. No maintainer server receives your data."
                    )
                    Text("Folder: \(folderStore.folderName)")
                }
                Section("Set up") {
                    Button("1. Allow Apple Health access") {
                        Task { await exporter.requestAuthorization() }
                    }
                    Button("2. Choose outbox folder") { choosingFolder = true }
                }
                Section("Export") {
                    Button("Export all running history") {
                        Task { await exporter.exportAll() }
                    }
                    Button("Export last 7 days") {
                        Task { await exporter.exportRecent() }
                    }
                    Text(exporter.status)
                    if exporter.isBusy { ProgressView() }
                }
                Section("What is preserved") {
                    Text(
                        "Route, timestamps, distance, heart rate, power, speed, stride length, "
                            + "vertical oscillation, and ground-contact time are exported only "
                            + "when Apple Health contains them. Cadence is never invented."
                    )
                }
            }
            .navigationTitle("NRC Volt Sync")
            .disabled(exporter.isBusy)
            .fileImporter(
                isPresented: $choosingFolder,
                allowedContentTypes: [.folder],
                allowsMultipleSelection: false
            ) { result in
                if case let .success(urls) = result, let url = urls.first {
                    do {
                        try folderStore.select(url)
                    } catch {
                        folderError = error.localizedDescription
                    }
                }
            }
            .alert(
                "Folder access failed",
                isPresented: Binding(
                    get: { folderError != nil },
                    set: { if !$0 { folderError = nil } }
                )
            ) {
                Button("OK", role: .cancel) { folderError = nil }
            } message: {
                Text(folderError ?? "Unknown folder error")
            }
        }
    }
}
