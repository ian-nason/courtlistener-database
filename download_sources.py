"""Stream and verify a pinned CourtListener source manifest without replacing cache."""
import argparse,hashlib,json,os,pathlib,tempfile,urllib.request

def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024**2),b''):digest.update(chunk)
    return digest.hexdigest()

def identity(url):
    with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30) as response:
        return {'size':int(response.headers['Content-Length']),'etag':response.headers.get('ETag'),'last_modified_http':response.headers.get('Last-Modified')}

def acquire(entry,raw):
    name=entry['file']
    if pathlib.Path(name).name!=name:raise ValueError('Source filename must be a basename')
    before=identity(entry['url'])
    if before['size']!=entry['size'] or ('etag' in entry and entry['etag']!=before['etag']):raise ValueError('Pinned source identity changed: '+name)
    path=raw/name
    if path.exists():
        if 'sha256' not in entry or path.stat().st_size!=entry['size'] or sha256(path)!=entry['sha256']:
            raise FileExistsError('Existing source is not the verified candidate: '+str(path))
        return dict(entry,**before,cache_verified=True)
    digest=hashlib.sha256();received=0
    with tempfile.NamedTemporaryFile(dir=raw,prefix=name+'.',suffix='.part',delete=False) as temporary:
        part=pathlib.Path(temporary.name)
        try:
            with urllib.request.urlopen(entry['url'],timeout=30) as response:
                if int(response.headers['Content-Length'])!=before['size'] or response.headers.get('ETag')!=before['etag']:raise ValueError('Source changed before GET: '+name)
                while chunk:=response.read(1024**2):
                    received+=len(chunk)
                    if received>entry['size']:raise ValueError('Source exceeded declared size: '+name)
                    temporary.write(chunk);digest.update(chunk)
            temporary.flush();os.fsync(temporary.fileno())
        except BaseException:
            # Retain the failed temporary bytes for diagnosis; never install them.
            raise
    if received!=entry['size']:raise ValueError('Truncated source: '+name)
    after=identity(entry['url'])
    if (after['size'],after['etag'])!=(before['size'],before['etag']):raise ValueError('Source changed after GET: '+name)
    if 'sha256' in entry and digest.hexdigest()!=entry['sha256']:raise ValueError('Pinned source checksum differs: '+name)
    # link() fails if another writer created the destination; it never overwrites.
    os.link(part,path);part.unlink()
    return dict(entry,**before,sha256=digest.hexdigest(),post_download_identity_verified=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=pathlib.Path,required=True);p.add_argument('--raw-dir',type=pathlib.Path,required=True);p.add_argument('--receipt',type=pathlib.Path,required=True);a=p.parse_args()
    manifest=json.loads(a.manifest.read_text());a.raw_dir.mkdir(parents=True,exist_ok=True)
    previous=json.loads(a.receipt.read_text()) if a.receipt.exists() else {}
    for key,entry in previous.items():
        if key not in manifest or any(manifest[key].get(k)!=entry.get(k) for k in ['file','url','size','etag']):raise ValueError('Prior receipt belongs to a different selection')
        manifest[key]=entry
    result=dict(previous)
    for key in sorted(manifest,key=lambda k:manifest[k]['size']):
        result[key]=acquire(manifest[key],a.raw_dir)
        temporary=a.receipt.with_suffix('.new');temporary.write_text(json.dumps(result,indent=2));temporary.replace(a.receipt)
        print(f"VERIFIED {key}: {result[key]['size']:,} bytes {result[key]['sha256']}",flush=True)
    print(f'ALL SOURCES VERIFIED: {len(result)}, {sum(x["size"] for x in result.values()):,} bytes',flush=True)

if __name__=='__main__':main()
