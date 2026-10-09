#!/usr/bin/env python3
"""Bounded Plex acceptance using mounted credentials in memory on ryback.

baseline is read-only. transcode starts/stops only its own short forced HLS
stream of existing media; never sends watch-state/timeline/library writes.
"""
import argparse
import json
import subprocess
import sys

REMOTE = r'''
import datetime, hashlib, json, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request, uuid
import xml.etree.ElementTree as ET

def kube(*args):
    return json.loads(subprocess.check_output(['sudo','-n','k3s','kubectl',*args,'-o','json'],stderr=subprocess.PIPE,text=True))

def context():
    pods=kube('get','pods','-n','plex')['items']
    matches=[(p,c) for p in pods if not p['metadata'].get('deletionTimestamp')
             for c in p['spec']['containers'] if any(s.get('ready') and s['name']==c['name'] for s in p['status'].get('containerStatuses',[]))
             and any(m['mountPath']=='/config' for m in c.get('volumeMounts',[]))]
    if len(matches)!=1: raise RuntimeError('Expected sole ready Plex config mount')
    pod,c=matches[0]
    raw=subprocess.check_output(['sudo','-n','k3s','kubectl','exec','-n','plex',pod['metadata']['name'],'-c',c['name'],'--','cat','/config/Library/Application Support/Plex Media Server/Preferences.xml'],stderr=subprocess.PIPE)
    prefs=ET.fromstring(raw).attrib
    headers={'X-Plex-Token':prefs['PlexOnlineToken'],'X-Plex-Client-Identifier':'homelab-gpu-acceptance'}
    def fetch(path, query=None, timeout=15):
        url='http://127.0.0.1:32400'+path
        if query: url+='?'+urllib.parse.urlencode(query)
        req=urllib.request.Request(url,headers=headers)
        with urllib.request.urlopen(req,timeout=timeout) as resp: return resp.read()
    identity=ET.fromstring(fetch('/identity')).get('machineIdentifier')
    if not identity or identity!=prefs.get('ProcessedMachineIdentifier'): raise RuntimeError('Server identity mismatch')
    return pod,c,prefs,headers,fetch,hashlib.sha256(identity.encode()).hexdigest()

def baseline():
    p,c,prefs,h,fetch,identity=context()
    pvc=kube('get','pvc','pms-config-plex-plex-media-server-0','-n','plex')
    sts=kube('get','sts','plex-plex-media-server','-n','plex')
    stat=p['status']['containerStatuses'][0]
    images={x['metadata']['namespace']+'/'+x['metadata']['name']+'/'+cc['name']:cc['image']
            for x in kube('get','pods','-A')['items'] for cc in x['spec']['containers']}
    return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),identity_sha256=identity,
                preferences={k:prefs.get(k) for k in ['HardwareAcceleratedCodecs','HardwareAcceleratedEncoders','TranscoderCanOnlyRemuxVideo','TranscoderQuality']},
                pod_uid=p['metadata']['uid'],image=c['image'],image_id=stat['imageID'],resources=c.get('resources'),
                security_context=c.get('securityContext'),pod_security_context=p['spec'].get('securityContext'),
                volume_mounts=c['volumeMounts'],volumes=p['spec']['volumes'],
                pvc_uid=pvc['metadata']['uid'],pvc_volume=pvc['spec']['volumeName'],pvc_phase=pvc['status']['phase'],
                statefulset_volume_claim_templates=sts['spec'].get('volumeClaimTemplates'),application_images=images)

def stop_owned_stream(fetch, session, own_keys):
    # Never stop another user's sessions. A successful stop response alone is
    # not proof of termination: verify absence in both playback/transcode lists.
    for attempt in range(3):
        try:
            fetch('/video/:/transcode/universal/stop', {'session': session}, timeout=5)
        except Exception:
            pass
        try:
            transcodes = ET.fromstring(fetch('/transcode/sessions', timeout=5))
            playbacks = ET.fromstring(fetch('/status/sessions', timeout=5))
            transcode_present = any(session in str(x.attrib) or x.get('key') in own_keys
                                    for x in transcodes.iter('TranscodeSession'))
            playback_present = any(v.find('Player') is not None
                                   and v.find('Player').get('machineIdentifier') == session
                                   for v in playbacks.findall('Video'))
            if not transcode_present and not playback_present:
                return True
        except Exception:
            pass
        if attempt < 2:
            time.sleep(1)
    return False

def transcode():
    p,c,prefs,headers,fetch,identity=context()
    session='homelab-gpu-'+str(uuid.uuid4())
    headers.update({'X-Plex-Client-Identifier':session,'X-Plex-Product':'Plex Web','X-Plex-Platform':'Chrome','X-Plex-Version':'1.0','X-Plex-Device':'GPU acceptance probe','X-Plex-Client-Profile-Name':'Chrome'})
    sections=ET.fromstring(fetch('/library/sections')).findall('Directory')
    candidates=[]
    for section in sections:
        if section.get('type') not in ['show','movie']: continue
        route='/library/sections/'+section.get('key')+('/allLeaves' if section.get('type')=='show' else '/all')
        root=ET.fromstring(fetch(route,{'sort':'duration:asc','X-Plex-Container-Start':0,'X-Plex-Container-Size':20}))
        for v in root.findall('Video'):
            media=v.find('Media'); part=media.find('Part') if media is not None else None
            if part is not None and media.get('videoCodec') in ['h264','hevc','mpeg4','mpeg2video']:
                candidates.append((int(v.get('duration','999999999')),v,media,part))
    if not candidates: raise RuntimeError('No existing representative video')
    _,v,media,part=min(candidates,key=lambda x:x[0])
    query={'path':'/library/metadata/'+v.get('ratingKey'),'mediaIndex':0,'partIndex':0,'protocol':'hls','offset':0,
           'fastSeek':1,'directPlay':0,'directStream':0,'videoResolution':'640x360','maxVideoBitrate':1000,'videoQuality':60,
           'audioBoost':100,'session':session,'subtitles':'none','subtitleSize':100,'copyts':1,'hasMDE':1}
    result=dict(identity_sha256=identity,session=session,source=dict(rating_key=v.get('ratingKey'),title=v.get('title'),
                duration_ms=v.get('duration'),codec=media.get('videoCodec'),width=media.get('width'),height=media.get('height'),size=part.get('size')),
                method='PMS universal forced HLS transcode, existing media, no timeline/scrobble',segments_read=0,session_evidence=[],hardware=False)
    deadline=time.monotonic()+75
    own_keys=set()
    stage='start-hls'
    try:
        playlist=fetch('/video/:/transcode/universal/start.m3u8',query,timeout=25).decode()
        # Follow playlist URLs with the token only in HTTP headers, never argv/logs.
        base='/video/:/transcode/universal/start.m3u8'
        for _ in range(3):
            stage='read-playlist-or-segment'
            links=[x.strip() for x in playlist.splitlines() if x.strip() and not x.startswith('#')]
            if not links: raise RuntimeError('Empty HLS playlist')
            link=urllib.parse.urljoin(base,links[0]); parsed=urllib.parse.urlsplit(link)
            if parsed.hostname and parsed.hostname not in ['127.0.0.1','localhost']: raise RuntimeError('Unexpected stream host')
            base=parsed.path+('?' + parsed.query if parsed.query else '')
            payload=fetch(base,timeout=20)
            if payload.startswith(b'#EXTM3U'): playlist=payload.decode(); continue
            if not payload: raise RuntimeError('Empty HLS segment')
            result['segments_read']+=1; result['segment_bytes']=len(payload); break
        while time.monotonic()<deadline:
            stage='inspect-own-transcode-session'
            root=ET.fromstring(fetch('/transcode/sessions'))
            owned=[x for x in root.iter('TranscodeSession') if session in str(x.attrib)]
            # Some PMS versions use a short key; also match current playback's session.
            sessions=ET.fromstring(fetch('/status/sessions'))
            for video in sessions.findall('Video'):
                player=video.find('Player'); trans=video.find('TranscodeSession')
                if player is not None and player.get('machineIdentifier')==session and trans is not None: owned.append(trans)
            allowed=['key','videoDecision','audioDecision','videoCodec','audioCodec','protocol','container','progress','speed','throttled',
                     'transcodeHwRequested','transcodeHwEncoding','transcodeHwDecoding','transcodeHwFullPipeline','transcodeHwEncodingTitle','transcodeHwDecodingTitle']
            for x in owned:
                if x.get('key'): own_keys.add(x.get('key'))
                evidence={k:x.get(k) for k in allowed if x.get(k) is not None}
                if evidence not in result['session_evidence']: result['session_evidence'].append(evidence)
                if (x.get('videoDecision')=='transcode'
                    and x.get('transcodeHwEncoding') not in [None,'','0']
                    and x.get('transcodeHwDecoding') not in [None,'','0']
                    and x.get('transcodeHwFullPipeline')=='1'):
                    result['hardware']=True
            if result['hardware'] and result['segments_read']: break
            time.sleep(2)
        result['passed']=result['hardware'] and result['segments_read']>0
    except Exception as error:
        result.update(passed=False,error_type=type(error).__name__,http_code=getattr(error,'code',None),stage=stage)
        if isinstance(error,urllib.error.HTTPError):
            body=error.read().decode(errors='replace')
            try:
                root=ET.fromstring(body)
                detail=root.get('message') or ' '.join(root.itertext())
            except ET.ParseError:
                detail=re.sub('<[^>]+>',' ',body)
            detail=detail.replace(headers['X-Plex-Token'],'[REDACTED]')
            result['server_error']=re.sub(r'https?://[^\s<>]+','[URL]',detail).strip()[:500]
    finally:
        result['own_stream_stopped']=stop_owned_stream(fetch,session,own_keys)
        result['passed']=bool(result.get('passed') and result['own_stream_stopped'])
        if not result['own_stream_stopped']:
            result['cleanup_error']='owned_session_termination_unverified'
    return result

try:
    result=transcode() if sys.argv[1]=='transcode' else baseline()
    print(json.dumps(result,indent=2))
except Exception as error:
    print(json.dumps({'passed':False,'error_type':type(error).__name__,'http_code':getattr(error,'code',None)}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["baseline", "transcode"])
    parser.add_argument("--host", default="192.168.1.110")
    parser.add_argument("--output")
    args = parser.parse_args()
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", args.host, "python3 - " + args.mode],
        input=REMOTE, text=True, capture_output=True, timeout=180, check=True,
    )
    result = json.loads(proc.stdout)
    if args.output:
        from pathlib import Path
        target = Path(args.output)
        target.write_text(json.dumps(result, indent=2) + "\n")
        target.chmod(0o600)
    print(json.dumps(result, indent=2))
    if args.mode == 'transcode':
        return 0 if result.get('passed') is True and result.get('own_stream_stopped') is True else 1
    return 1 if result.get("passed") is False else 0


if __name__ == "__main__":
    sys.exit(main())
