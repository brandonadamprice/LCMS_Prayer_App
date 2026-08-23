import Foundation
import UIKit
import Capacitor

/**
 * window.print() is a silent no-op inside an iOS WKWebView (same as the
 * Android WebView), so the web Print button hands the page to this plugin
 * instead (app.js printPage()). It feeds the WebView's own print formatter
 * to UIPrintInteractionController, which renders the page with @media print
 * styles applied — the same handout the desktop print path produces.
 * iOS counterpart of PrinterPlugin.java; registered in MainViewController.
 */
@objc(PrinterPlugin)
public class PrinterPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "PrinterPlugin"
    public let jsName = "Printer"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "print", returnType: CAPPluginReturnPromise)
    ]

    @objc func print(_ call: CAPPluginCall) {
        let jobName = call.getString("name") ?? "A Simple Way to Pray"
        DispatchQueue.main.async {
            guard let webView = self.bridge?.webView else {
                call.reject("Print failed: no web view")
                return
            }
            let printInfo = UIPrintInfo(dictionary: nil)
            printInfo.jobName = jobName
            printInfo.outputType = .general
            let controller = UIPrintInteractionController.shared
            controller.printInfo = printInfo
            controller.printFormatter = webView.viewPrintFormatter()
            // Resolve whether the user prints or cancels — the Android path
            // resolves on handing off to PrintManager the same way.
            controller.present(animated: true) { _, _, error in
                if let error = error {
                    call.reject("Print failed: \(error.localizedDescription)")
                } else {
                    call.resolve()
                }
            }
        }
    }
}
