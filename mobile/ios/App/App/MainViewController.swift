import UIKit
import Capacitor

// iOS counterpart of MainActivity.java: the storyboard instantiates this
// subclass so the in-repo Printer plugin gets registered with the bridge.
class MainViewController: CAPBridgeViewController {
    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(PrinterPlugin())
    }
}
