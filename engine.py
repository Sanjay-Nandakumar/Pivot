import math
from datetime import datetime, time, timedelta
import pandas as pd

METHODS = ['Traditional Pivot S1/R1','Camarilla Pivot R1/S1','Camarilla Pivot R2/S2','Manual Offset From Central Pivot Point']
DURATIONS = {'1 Hour':60,'90 Minutes':90,'2 Hours':120,'1 Day':None}

def calculate(high, low, previous_close, trigger, method=METHODS[0], manual_offset=0., step=None, call_offset=0., put_offset=0.):
    vals = [high,low,previous_close,trigger]
    if not all(math.isfinite(float(v)) for v in vals) or low > high or step is not None and step <= 0:
        raise ValueError('Invalid HLC, trigger, or strike interval')
    cp=(high+low+previous_close)/3
    bc=(high+low)/2
    tc=2*cp-bc
    top,bottom=max(bc,tc),min(bc,tc)
    r1,s1=2*cp-low,2*cp-high
    rng=high-low
    cr1,cs1=previous_close+rng*1.1/12,previous_close-rng*1.1/12
    cr2,cs2=previous_close+rng*1.1/6,previous_close-rng*1.1/6
    if method == METHODS[0]:
        ct,pt=s1,r1
        call_src,put_src=max(high,r1),min(low,s1)
    elif method == METHODS[1]:
        ct,pt=cs1,cr1
        call_src,put_src=max(high,cr1),min(low,cs1)
    elif method == METHODS[2]:
        ct,pt=cs2,cr2
        call_src,put_src=max(high,cr2),min(low,cs2)
    elif method == METHODS[3]:
        ct=pt=cp
        call_src,put_src=cp+manual_offset,cp-manual_offset
    else:
        raise ValueError('Unknown method')
    if step is None:
        step=50 if trigger>=1000 else 10 if trigger>=500 else 5 if trigger>=100 else 2.5 if trigger>=50 else 1 if trigger>=20 else .5
    ceil=lambda x: round(math.ceil((x-1e-10)/step)*step,8)
    floor=lambda x: round(math.floor((x+1e-10)/step)*step,8)
    call=ceil(top if trigger<ct else (cp+call_src)/2)
    put=floor(bottom if trigger>pt else (cp+put_src)/2)
    iccall,icput=ceil(r1),floor(s1)
    direction='Sell Put' if trigger>top else 'Sell Call' if trigger<bottom else 'Sell IC' if bottom<trigger<top else 'No Trade (boundary)'
    original={'Call':call,'Put':put,'IC Call':iccall,'IC Put':icput}
    adjusted={'Call':ceil(call+call_offset),'Put':floor(put+put_offset),'IC Call':ceil(iccall+call_offset),'IC Put':floor(icput+put_offset)}
    chosen={'Sell Call':f"{adjusted['Call']:g}",'Sell Put':f"{adjusted['Put']:g}",'Sell IC':f"{adjusted['IC Call']:g} / {adjusted['IC Put']:g}"}.get(direction,'—')
    return dict(cp=cp,top=top,bottom=bottom,r1=r1,s1=s1,call_trigger=ct,put_trigger=pt,direction=direction,original=original,adjusted=adjusted,selected=chosen,step=step)

def wins(signal, strikes, settlement):
    if signal=='Sell Put': return settlement>strikes['Put']
    if signal=='Sell Call': return settlement<strikes['Call']
    if signal=='Sell IC': return strikes['IC Put']<settlement<strikes['IC Call']
    return False

def normalize_csv(file):
    df=pd.read_csv(file)
    df.columns=[str(c).strip().lower() for c in df.columns]
    if 'datetime' not in df and {'date','time'}.issubset(df):
        df['datetime']=df['date'].astype(str)+' '+df['time'].astype(str)
    required={'datetime','open','high','low','close'}
    if not required.issubset(df): raise ValueError('CSV must contain datetime, open, high, low, close (or date + time).')
    df['datetime']=pd.to_datetime(df['datetime'],errors='coerce')
    if df['datetime'].dt.tz is not None:
        df['datetime']=df['datetime'].dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
    for c in ['open','high','low','close']: df[c]=pd.to_numeric(df[c],errors='coerce')
    df=df.dropna(subset=['datetime','open','high','low','close']).sort_values('datetime').drop_duplicates('datetime')
    df=df[(df.datetime.dt.hour*60+df.datetime.dt.minute>=555)&(df.datetime.dt.hour*60+df.datetime.dt.minute<930)].copy()
    if df.empty: raise ValueError('No NSE regular-session bars in CSV. Datetimes should be in IST.')
    if len(df)>1 and not (df.datetime.diff().dropna().dt.total_seconds().div(60).mod(3).eq(0)).all():
        raise ValueError('Expected 3-minute aligned candle timestamps.')
    df['date']=df.datetime.dt.date
    df['minute']=df.datetime.dt.hour*60+df.datetime.dt.minute
    return df

def backtest(df,duration,start_minute,method,manual_offset,step,call_offset,put_offset):
    # Require full 3-minute session/window and a confirmed 3-minute trigger candle.
    days=sorted(df.date.unique())
    groups={d:g.set_index('minute') for d,g in df.groupby('date')}
    outcomes=[]
    window_length=DURATIONS[duration]
    if window_length is not None and (start_minute<555 or (start_minute-555)%3 or start_minute+window_length+3>930):
        raise ValueError('Window must align to 3-minute NSE candles and leave a confirmation candle.')
    for i,d in enumerate(days):
        g=groups[d]
        if window_length is None:
            if i==0: continue
            prior=groups[days[i-1]]
            if not set(range(555,930,3)).issubset(prior.index): continue
            h,l,c=prior.high.max(),prior.low.min(),float(prior.loc[927,'close'])
            entry=555
        else:
            end=start_minute+window_length
            if not set(range(start_minute,end,3)).issubset(g.index):continue
            window=g.loc[list(range(start_minute,end,3))]
            h,l,c=window.high.max(),window.low.min(),float(window.iloc[-1]['close'])
            entry=end
        if entry not in g.index or i+1>=len(days): continue
        nextg=groups[days[i+1]]
        exitminute=930 if window_length is None else start_minute+window_length
        exitbar=927 if window_length is None else exitminute-3
        if exitbar not in nextg.index:continue
        # This is the last candle before the next day's corresponding boundary.
        settlement=float(nextg.loc[exitbar,'close'])
        trigger=float(g.loc[entry,'close'])
        r=calculate(h,l,c,trigger,method,manual_offset,step,call_offset,put_offset)
        if r['direction'].startswith('No Trade'):continue
        outcomes.append({'Entry date':str(d),'Exit date':str(days[i+1]),'Type':r['direction'],'Trigger close':trigger,'Original strike':r['original']['Put' if r['direction']=='Sell Put' else 'Call'] if r['direction']!='Sell IC' else f"{r['original']['IC Call']:g}/{r['original']['IC Put']:g}",'Adjusted strike':r['selected'],'Settlement':settlement,'Original win':wins(r['direction'],r['original'],settlement),'Adjusted win':wins(r['direction'],r['adjusted'],settlement)})
    return pd.DataFrame(outcomes)
