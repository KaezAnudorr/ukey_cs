import Foundation
import Virtualization

@main
final class RunVM: NSObject, VZVirtualMachineDelegate {
    func guestDidStop(_ virtualMachine: VZVirtualMachine) {
        exit(EXIT_SUCCESS)
    }

    func virtualMachine(_ virtualMachine: VZVirtualMachine, didStopWithError error: Error) {
        fputs("Virtual machine stopped: \(error)\n", stderr)
        exit(EXIT_FAILURE)
    }

    static func main() {
        do {
            guard CommandLine.arguments.count == 5 else {
                fputs("Usage: RunVM disk.raw seed.iso share-directory efi-store\n", stderr)
                exit(EXIT_FAILURE)
            }
            let paths = CommandLine.arguments.dropFirst().map { URL(fileURLWithPath: $0) }
            let config = VZVirtualMachineConfiguration()
            config.cpuCount = 2
            config.memorySize = 3 * 1024 * 1024 * 1024
            let boot = VZEFIBootLoader()
            boot.variableStore = try VZEFIVariableStore(creatingVariableStoreAt: paths[3])
            config.bootLoader = boot
            config.storageDevices = try [false, true].enumerated().map { index, readOnly in
                let disk = try VZDiskImageStorageDeviceAttachment(url: paths[index], readOnly: readOnly)
                return VZVirtioBlockDeviceConfiguration(attachment: disk)
            }
            let share = VZVirtioFileSystemDeviceConfiguration(tag: "cs-lab")
            share.share = VZSingleDirectoryShare(directory: VZSharedDirectory(url: paths[2], readOnly: false))
            config.directorySharingDevices = [share]
            let network = VZVirtioNetworkDeviceConfiguration()
            network.attachment = VZNATNetworkDeviceAttachment()
            config.networkDevices = [network]
            config.entropyDevices = [VZVirtioEntropyDeviceConfiguration()]
            let console = VZVirtioConsoleDeviceSerialPortConfiguration()
            console.attachment = VZFileHandleSerialPortAttachment(
                fileHandleForReading: nil,
                fileHandleForWriting: FileHandle.standardOutput
            )
            config.serialPorts = [console]
            try config.validate()
            let runner = RunVM()
            let machine = VZVirtualMachine(configuration: config)
            machine.delegate = runner
            machine.start { result in
                if case let .failure(error) = result {
                    fputs("Virtual machine startup failed: \(error)\n", stderr)
                    exit(EXIT_FAILURE)
                }
            }
            withExtendedLifetime((machine, runner)) { RunLoop.main.run() }
        } catch {
            fputs("Cannot launch virtual machine: \(error)\n", stderr)
            exit(EXIT_FAILURE)
        }
    }
}
