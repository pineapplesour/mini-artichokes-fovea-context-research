import UIKit
import WebKit

final class NativeShellViewController: UIViewController, WKNavigationDelegate {
    private let productKey: String
    private let openChat: Bool
    private let allowedOrigin: URL
    private var webView: WKWebView!

    init(productKey: String = "islam", openChat: Bool = false, baseOrigin: URL = URL(string: "https://example.invalid")!) {
        self.productKey = productKey
        self.openChat = openChat
        self.allowedOrigin = baseOrigin
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) {
        self.productKey = "islam"
        self.openChat = false
        self.allowedOrigin = URL(string: "https://example.invalid")!
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.allowsInlineMediaPlayback = false
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.topAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
        webView.load(URLRequest(url: routeURL()))
    }

    private func routeURL() -> URL {
        let manifest = readAppShellManifest()
        guard
            let products = manifest["products"] as? [String: Any],
            let product = products[productKey] as? [String: Any],
            let native = product["native"] as? [String: Any]
        else {
            preconditionFailure("Missing product in app-shell-manifest")
        }
        let routeKey = openChat ? "chatRoute" : "entryRoute"
        guard let route = native[routeKey] as? String else {
            preconditionFailure("Missing native route")
        }
        // Keep these reads explicit so the native wrapper stays tied to web storage policy.
        _ = native["offlineStore"] as? String
        _ = native["sessionTokenStore"] as? String
        _ = native["accountSubjectStore"] as? String
        return URL(string: route, relativeTo: allowedOrigin)!.absoluteURL
    }

    private func readAppShellManifest() -> [String: Any] {
        guard let url = Bundle.main.url(forResource: "app-shell-manifest", withExtension: "json") else {
            preconditionFailure("Missing app-shell-manifest.json")
        }
        guard
            let data = try? Data(contentsOf: url),
            let json = try? JSONSerialization.jsonObject(with: data),
            let manifest = json as? [String: Any]
        else {
            preconditionFailure("Invalid app-shell-manifest.json")
        }
        return manifest
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }
        decisionHandler(isAllowed(url) ? .allow : .cancel)
    }

    private func isAllowed(_ url: URL) -> Bool {
        let lhs = URLComponents(url: url, resolvingAgainstBaseURL: true)
        let rhs = URLComponents(url: allowedOrigin, resolvingAgainstBaseURL: true)
        return lhs?.scheme == rhs?.scheme && lhs?.host == rhs?.host && lhs?.port == rhs?.port
    }
}
