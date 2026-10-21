"""Non-neural visual metadata/CA colour cues. Never an NSFW clearance model."""
import io
import json
import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path


def features(image):
    # Integer pixel rules and binary-cell majority updates, no semantic model.
    import numpy as np
    rgba=image.convert('RGBA');background=__import__('PIL.Image',fromlist=['Image']).new('RGBA',rgba.size,'white');background.alpha_composite(rgba)
    rgb=np.asarray(background.convert('RGB').resize((64,64)),dtype=np.int32)
    r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
    warm=(r>60)&(g>35)&(b>20)&(r>g)&(r>b)&(abs(r-g)>10)&((rgb.max(axis=2)-rgb.min(axis=2))>15)
    for _ in range(3):
        padded=np.pad(warm.astype(np.int32),1);neighbors=sum(padded[dy:dy+64,dx:dx+64] for dy in range(3) for dx in range(3));warm=neighbors>=5
    seen=set();largest=0
    for y,x in zip(*np.where(warm)):
        point=(int(y),int(x))
        if point in seen:continue
        pending=[point];seen.add(point);size=0
        while pending:
            cy,cx=pending.pop();size+=1
            for ny,nx in ((cy-1,cx),(cy+1,cx),(cy,cx-1),(cy,cx+1)):
                if 0<=ny<64 and 0<=nx<64 and warm[ny,nx] and (ny,nx) not in seen:seen.add((ny,nx));pending.append((ny,nx))
        largest=max(largest,size)
    means=rgb.mean(axis=(0,1)).astype(int).tolist();coverage=int(warm.sum())*10000//4096;region=largest*10000//4096
    return dict(mean_rgb=means,warm_region_basis_points=coverage,largest_warm_region_basis_points=region,
                coarse_colour_cue=coverage>=2500 and region>=1500,analysis='integer RGB rules plus three binary-cell majority steps')


def assessment(frames,**metadata):
    cue=any(f['coarse_colour_cue'] for f in frames)
    return dict(status='analyzed',metadata=metadata,frames=frames,priority='elevated' if cue else 'normal',
                suspected_nsfw=None,signals=['coarse_warm_colour_region'] if cue else [],requires_human_review=True,
                auto_approved=False,auto_blurred=False,moderation_complete=False,
                limitation='Colour/shape cues are not nudity detection or semantic image understanding; clothing, backgrounds and lighting can trigger them. Absence of a cue never clears content.')


def image(blob):
    from PIL import Image,ImageOps
    with warnings.catch_warnings():
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(blob)) as decoded:
            if decoded.format not in {'PNG','JPEG','WEBP','GIF','BMP'}:raise ValueError('Unsupported image format')
            if decoded.width*decoded.height>16_000_000:raise ValueError('Image pixel limit')
            count=getattr(decoded,'n_frames',1)
            if count>1000:raise ValueError('Animation frame limit')
            indices=sorted({round(i*(count-1)/min(11,count-1)) for i in range(min(12,count))}) if count>1 else [0]
            frames=[]
            for index in indices:
                decoded.seek(index);decoded.load();frame=ImageOps.exif_transpose(decoded.copy());frames.append(dict(frame=index,**features(frame)))
            return assessment(frames,width=decoded.width,height=decoded.height,format=decoded.format,frame_count=count,
                              sampled_frames=len(frames),full_frame_coverage=len(frames)==count,neural_model=False)


def video(blob):
    from PIL import Image
    ffmpeg,ffprobe=shutil.which('ffmpeg'),shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:raise ValueError('Video decoder unavailable; manual review required')
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    with tempfile.TemporaryDirectory(prefix='cael-media-') as folder:
        source=Path(folder)/'upload.bin';source.write_bytes(blob)
        common=['-protocol_whitelist','file,pipe','-format_whitelist','mov,matroska,webm,avi']
        probe=subprocess.run([ffprobe,'-v','error','-threads','1',*common,'-show_entries','format=duration:stream=codec_type,width,height','-of','json',str(source)],capture_output=True,timeout=8,creationflags=flags)
        if probe.returncode:raise ValueError('Video metadata could not be decoded')
        metadata=json.loads(probe.stdout);duration=float(metadata.get('format',{}).get('duration',0))
        if not 0<duration<=600:raise ValueError('Video duration must be available and at most 600 seconds')
        streams=[s for s in metadata.get('streams',[]) if s.get('codec_type')=='video']
        if not streams or streams[0].get('width',0)*streams[0].get('height',0)>16_000_000:raise ValueError('Video stream/pixel limit')
        times=sorted({round(min(max(0,duration-.05),duration*i/12),3) for i in range(12)})
        frames=[];failed=[]
        for stamp in times:
            result=subprocess.run([ffmpeg,'-v','error','-nostdin','-threads','1',*common,'-ss',str(stamp),'-i',str(source),'-map','0:v:0','-frames:v','1','-vf','scale=128:128','-threads','1','-f','image2pipe','-vcodec','png','pipe:1'],capture_output=True,timeout=6,creationflags=flags)
            if result.returncode or not result.stdout:failed.append(stamp);continue
            with Image.open(io.BytesIO(result.stdout)) as frame:frames.append(dict(seconds=stamp,**features(frame)))
        if not frames:raise ValueError('No video sample decoded; manual review required')
        report=assessment(frames,duration_seconds=duration,width=streams[0].get('width'),height=streams[0].get('height'),
                          sampled_frames=len(frames),failed_timestamps=failed,full_frame_coverage=False,neural_model=False)
        report['limitation']+=' Video is sparsely sampled; brief events and unsampled frames can be missed.'
        return report
