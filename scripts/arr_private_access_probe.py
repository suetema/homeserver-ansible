"""Credential-free snapshots and anonymous HTTPS probes for the approved repair.

Remote mode runs via SSH with this file on stdin. All application API requests
are GETs; credentials remain in memory on ryback. This helper never changes state.
"""

import concurrent.futures
import datetime
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def anonymous(url, headers=None):
    try:
        opener = urllib.request.build_opener(NoRedirect)
        try:
            response = opener.open(
                urllib.request.Request(url, headers=headers or {}), timeout=15
            )
        except urllib.error.HTTPError as error:
            response = error
        with response:
            challenge = response.headers.get("WWW-Authenticate", "")
            return {
                "status": response.code,
                "basic_challenge": challenge.startswith("Basic "),
                "location_path": urllib.parse.urlsplit(
                    response.headers.get("Location", "")
                ).path,
                "tls_validated": url.startswith("https://"),
            }
    except Exception as error:
        return {"error": type(error).__name__, "tls_validated": False}


def kube(kind, namespace=None):
    command = ["sudo", "-n", "k3s", "kubectl", "get", kind]
    command += ["-n", namespace] if namespace else ["-A"]
    command += ["-o", "json"]
    result = subprocess.run(command, capture_output=True, check=True)
    return json.loads(result.stdout)["items"]


def remote():
    pods = kube("pods")
    flux = kube("helmreleases,kustomizations")
    ingresses = kube("ingresses")
    services = kube("svc", "ingress-nginx")
    service = next(s for s in services if s["metadata"]["name"] == "ingress-nginx-controller")
    result = {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pods": [
            {
                "namespace": p["metadata"]["namespace"],
                "name": p["metadata"]["name"],
                "uid": p["metadata"]["uid"],
                "phase": p["status"].get("phase"),
                "deleting": bool(p["metadata"].get("deletionTimestamp")),
                "podIP": p["status"].get("podIP"),
                "ready": any(c["type"] == "Ready" and c["status"] == "True"
                             for c in p["status"].get("conditions", [])),
                "containers": [
                    {key: c.get(key) for key in ["name", "image", "imageID", "restartCount"]}
                    for c in p["status"].get("containerStatuses", [])
                ],
                "gpu_resources": [
                    c.get("resources", {}) for c in p["spec"].get("containers", [])
                    if p["metadata"]["namespace"] == "plex"
                ],
            }
            for p in pods
        ],
        "flux": [
            {
                "namespace": x["metadata"]["namespace"],
                "name": x["metadata"]["name"],
                "kind": x["kind"],
                "generation": x["metadata"]["generation"],
                "observedGeneration": x.get("status", {}).get("observedGeneration"),
                "ready": any(c["type"] == "Ready" and c["status"] == "True"
                             for c in x.get("status", {}).get("conditions", [])),
                "revision": x.get("status", {}).get("lastAppliedRevision")
                            or x.get("status", {}).get("lastAttemptedRevision"),
            }
            for x in flux
        ],
        "ingress_service": {
            "externalTrafficPolicy": service["spec"].get("externalTrafficPolicy"),
            "loadBalancer": service["status"].get("loadBalancer"),
        },
        "nginx_hosts": sorted({r["host"] for i in ingresses
                               if i["spec"].get("ingressClassName") == "nginx"
                               for r in i["spec"].get("rules", [])}),
        "apps": {},
    }
    for app, port in [("sonarr", 8989), ("radarr", 7878)]:
        root = ET.parse("/etc/k8sconfigs/" + app + "/config.xml").getroot()
        service = next(s for s in kube("svc", app) if s["metadata"]["name"] == app)
        base = "http://" + service["spec"]["clusterIP"] + ":" + str(port)
        headers = {"X-Api-Key": root.findtext("ApiKey")}

        def get(endpoint):
            with urllib.request.urlopen(
                urllib.request.Request(base + "/api/v3/" + endpoint, headers=headers),
                timeout=15,
            ) as response:
                return json.load(response)

        status, host = get("system/status"), get("config/host")
        result["apps"][app] = {
            "status": {k: status.get(k) for k in ["version", "startTime"]},
            "host": {k: host.get(k) for k in ["authenticationMethod", "authenticationRequired",
                                              "trustedNetworks", "trustCgnatIpAddresses"]},
            "profile_ids": sorted(p["id"] for p in get("qualityprofile")),
            "library_count": len(get("series" if app == "sonarr" else "movie")),
            "root_folders": sorted(r["path"] for r in get("rootfolder")),
            "anonymous_direct": anonymous(base + "/"),
            "anonymous_api": anonymous(base + "/api/v3/system/status"),
            "anonymous_https": anonymous("https://" + app + ".suetens.cc/"),
        }
    return result


def web(snapshot):
    def check(host):
        return host, anonymous("https://" + host + "/")

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        return dict(pool.map(check, snapshot["nginx_hosts"]))


def main():
    if sys.argv[1:] == ["remote"]:
        print(json.dumps(remote(), indent=2))
    elif len(sys.argv) == 3 and sys.argv[1] == "web":
        with open(sys.argv[2]) as handle:
            snapshot = json.load(handle)
        print(json.dumps(web(snapshot), indent=2))
    else:
        raise ValueError("Expected remote or web SNAPSHOT.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never emit token-bearing URLs, exception details, or raw responses.
        print(json.dumps({"probe_error": type(error).__name__}))
        sys.exit(1)
