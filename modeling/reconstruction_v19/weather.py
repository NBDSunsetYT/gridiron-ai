"""Original operational NOAA GFS ranges, not reanalysis or inferred issue times.
Anonymous public S3 reads only. Exact object upload/version timestamps must
precede cutoff; initialization time alone is insufficient publication evidence.
"""
from urllib.request import Request,urlopen
from datetime import datetime,timedelta,timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import hashlib,json,math
from .evidence import aware

def fetch_field_ranges(run,lead,latitude,longitude,cutoff,folder):
    if not isinstance(lead,int) or not 0<=lead<=120:raise ValueError('This bounded archive reader supports hourly f000..f120')
    if not -90<=latitude<=90 or not -180<=longitude<=180:raise ValueError('Invalid public venue coordinates')
    init=aware(run)
    if init>=aware(cutoff):raise ValueError('Forecast initialization is after prediction cutoff')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);base=f'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{init:%Y%m%d}/{init:%H}/atmos/gfs.t{init:%H}z.pgrb2.0p25.f{lead:03d}'
    with urlopen(base+'.idx',timeout=20) as r:
        index=r.read(100001)
        if len(index)>100000:raise ValueError('GFS index exceeds request budget')
    rows=[line.split(':') for line in index.decode().splitlines() if line];offsets=sorted({int(r[1]) for r in rows});wanted=[('TMP','2 m above ground','temperature'),('UGRD','10 m above ground','u_wind'),('VGRD','10 m above ground','v_wind')];fields={};proof=[]
    from eccodes import codes_grib_new_from_file,codes_get,codes_grib_find_nearest,codes_release
    for variable,level,name in wanted:
        matches=[r for r in rows if len(r)>5 and r[3]==variable and r[4]==level]
        if len(matches)!=1:raise ValueError('GFS field identity is missing/ambiguous: '+name)
        offset=int(matches[0][1]);end=next((x-1 for x in offsets if x>offset),None)
        if end is None or end-offset+1>8000000:raise ValueError('Unbounded or oversized GFS field range')
        with urlopen(Request(base,headers={'Range':f'bytes={offset}-{end}'}),timeout=25) as r:
            if r.status!=206 or r.headers.get('Content-Range','').split('/')[0]!=f'bytes {offset}-{end}':raise ValueError('Server did not honor bounded byte range; full object download refused')
            modified=r.headers.get('Last-Modified')
            if not modified:raise ValueError('Original object version timestamp unavailable')
            published=parsedate_to_datetime(modified).astimezone(timezone.utc)
            if published>=aware(cutoff):raise ValueError('Source version was uploaded after prediction cutoff')
            data=r.read(end-offset+2)
            if len(data)!=end-offset+1 or not data.startswith(b'GRIB'):raise ValueError('GRIB range length/content mismatch')
        sha=hashlib.sha256(data).hexdigest();path=folder/(sha+'.grib')
        if not path.exists():path.write_bytes(data)
        with path.open('rb') as f:
            gid=codes_grib_new_from_file(f)
            if gid is None:raise ValueError('GRIB field decode failed')
            try:
                date=int(codes_get(gid,'dataDate'));hour=int(codes_get(gid,'dataTime'));step=int(codes_get(gid,'endStep'))
                if date!=int(init.strftime('%Y%m%d')) or hour!=init.hour*100 or step!=lead:raise ValueError('Forecast run/lead mapping failed')
                identity=(str(codes_get(gid,'shortName')),str(codes_get(gid,'typeOfLevel')),int(codes_get(gid,'level')))
                expected={'temperature':('2t','heightAboveGround',2),'u_wind':('10u','heightAboveGround',10),'v_wind':('10v','heightAboveGround',10)}[name]
                if identity!=expected:raise ValueError('Decoded weather variable/level disagrees with index')
                nearest=codes_grib_find_nearest(gid,latitude,longitude%360,npoints=1)[0];value=float(nearest['value']);fields[name]=value;units=str(codes_get(gid,'units'))
                proof.append({'field':name,'source':base,'range':[offset,end],'bytes':len(data),'sha256':sha,'sourceVersionPublishedAt':published.isoformat(),'forecastInitializedAt':init.isoformat(),'forecastValidAt':(init+timedelta(hours=lead)).isoformat(),'units':units,'nearestGridLatitude':float(nearest['lat']),'nearestGridLongitude':float(nearest['lon']),'distanceKm':float(nearest['distance'])})
            finally:codes_release(gid)
    return {'source':'NOAA operational GFS via anonymous NODD S3','run':run,'leadHours':lead,'latitude':latitude,'longitude':longitude,'cutoff':cutoff,'temperatureCelsius':fields['temperature']-273.15,'windSpeedKph':math.hypot(fields['u_wind'],fields['v_wind'])*3.6,'fields':proof,'indexSha256':hashlib.sha256(index).hexdigest(),'retrievedAt':datetime.now(timezone.utc).isoformat(),'isObservedWeather':False,'isReanalysis':False,'modelEffectApplied':False,'modelEffectReason':'New provenance-qualified weather evidence; a learned, independently validated weather response is not available for this frozen model experiment.'}
