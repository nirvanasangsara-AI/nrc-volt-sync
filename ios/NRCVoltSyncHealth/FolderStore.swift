import Foundation
import HealthOutboxCore

enum FolderStoreError: LocalizedError {
    case noFolder
    case accessDenied

    var errorDescription: String? {
        switch self {
        case .noFolder:
            "Choose an iCloud Drive or Files folder first."
        case .accessDenied:
            "The selected folder is no longer accessible. Choose it again."
        }
    }
}

@MainActor
final class FolderStore: ObservableObject {
    @Published private(set) var folderName = "No folder selected"
    private let bookmarkKey = "healthOutboxFolderBookmark"

    init() {
        refreshName()
    }

    func select(_ url: URL) throws {
        let accessed = url.startAccessingSecurityScopedResource()
        defer {
            if accessed { url.stopAccessingSecurityScopedResource() }
        }
        let bookmark = try url.bookmarkData(
            options: .minimalBookmark,
            includingResourceValuesForKeys: nil,
            relativeTo: nil
        )
        UserDefaults.standard.set(bookmark, forKey: bookmarkKey)
        folderName = url.lastPathComponent
    }

    func write(_ payload: HealthWorkoutPayload) throws {
        let url = try resolvedFolder()
        guard url.startAccessingSecurityScopedResource() else {
            throw FolderStoreError.accessDenied
        }
        defer { url.stopAccessingSecurityScopedResource() }
        let data = try PayloadEncoder.encode(payload)
        let destination = url.appendingPathComponent(payload.id.uuidString.lowercased())
            .appendingPathExtension("json")
        try data.write(to: destination, options: [.atomic, .completeFileProtection])
    }

    private func refreshName() {
        guard let url = try? resolvedFolder() else { return }
        folderName = url.lastPathComponent
    }

    private func resolvedFolder() throws -> URL {
        guard let bookmark = UserDefaults.standard.data(forKey: bookmarkKey) else {
            throw FolderStoreError.noFolder
        }
        var stale = false
        let url = try URL(
            resolvingBookmarkData: bookmark,
            options: [.withoutUI],
            relativeTo: nil,
            bookmarkDataIsStale: &stale
        )
        if stale {
            try select(url)
        }
        return url
    }
}
