import streamlit as st
import pandas as pd
from datetime import time
from engine import calculate, normalize_csv, backtest, METHODS, DURATIONS

st.set_page_config(page_title='CPR Price Simulator',page_icon='📈',layout='wide')
st.title('CPR Option Sale — Price Simulator')
st.caption('Manual what-if calculator based on the supplied Pine Script. No live market feed, broker integration, or option-premium P&L.')
with st.sidebar:
    st.header('Pivot settings')
    duration=st.selectbox('Pivot duration',list(DURATIONS),index=3)
    start=time(11,15)
    if duration!='1 Day':
        start=st.time_input('Pivot window starts (exchange time, IST)',value=time(11,15),step=180)
        start_min=start.hour*60+start.minute
        end=start_min+DURATIONS[duration]
        if (start_min-555)%3 or start_min<555 or end+3>930:
            st.error('Use a 3-minute-aligned start from 09:15 and leave a complete 3-minute trigger candle before 15:30.')
            st.stop()
        st.caption(f'Window: {start.hour:02d}:{start.minute:02d}–{end//60:02d}:{end%60:02d}; trigger close at {(end+3)//60:02d}:{(end+3)%60:02d}')
    else:
        start_min=555
        st.caption('Daily mode: previous completed NSE session HLC; next session 09:15–09:18 trigger candle close.')
    method=st.selectbox('Near strike calculation',METHODS)
    manual_offset=st.number_input('Manual offset from CP',value=0.,step=25.) if method==METHODS[3] else 0.
    auto_step=st.checkbox('Automatic strike interval (Pine behavior)',value=False)
    step=None if auto_step else st.number_input('Strike interval (points)',min_value=0.01,value=50.,step=5.)
    call_offset=st.number_input('Call strike offset',value=0.,step=25.)
    put_offset=st.number_input('Put strike offset',value=0.,step=25.)

st.subheader('1. Enter completed pivot HLC and predicted trigger close')
st.info('Enter the HLC of the **completed reference window**. For tomorrow’s daily simulation, use today’s completed session HLC. For an intraday window, use that window’s HLC. The predicted price is the **first 3-minute candle close after the window**, not its opening price.')
c1,c2,c3,c4=st.columns(4)
with c1: high=st.number_input('Reference high',min_value=0.01,value=23400.,step=25.)
with c2: low=st.number_input('Reference low',min_value=0.01,value=23100.,step=25.)
with c3: refclose=st.number_input('Reference close',min_value=0.01,value=23300.,step=25.)
with c4: price=st.number_input('Predicted trigger candle close',min_value=0.01,value=23300.,step=25.)
if not(low<=refclose<=high):
    st.error('Reference close must be between reference low and high.')
    st.stop()
try:
    result=calculate(high,low,refclose,price,method,manual_offset,step,call_offset,put_offset)
except ValueError as e:
    st.error(str(e));st.stop()

st.subheader('2. Simulated recommendation')
a,b,c,d=st.columns(4)
a.metric('Signal',result['direction'])
b.metric('ACTUAL SIGNAL STRIKE',result['selected'])
c.metric('CPR Top',f"{result['top']:.2f}")
d.metric('CPR Bottom',f"{result['bottom']:.2f}")
st.caption(f"CPR Central: {result['cp']:.2f}  |  R1: {result['r1']:.2f}  |  S1: {result['s1']:.2f}  |  Strike step: {result['step']:g}")
strikes=pd.DataFrame([{'Side':k,'Original':v,'Adjusted':result['adjusted'][k]} for k,v in result['original'].items()])
st.dataframe(strikes,hide_index=True,use_container_width=True)
st.caption('Call/Put reference strikes are shown for comparison. Only the side selected by Signal is recommended by the simulation. IC displays sell Call / sell Put.')

st.subheader('3. Historical accuracy (optional CSV)')
st.write('Upload **3-minute NSE OHLC** candles with columns `datetime,open,high,low,close` (IST, candle **opening** timestamp). A date/time pair of columns also works. The backtest uses actual confirmed trigger closes, not your manual predicted price.')
file=st.file_uploader('3-minute OHLC CSV',type=['csv'])
if file:
    try:
        df=normalize_csv(file)
        outcomes=backtest(df,duration,start_min,method,manual_offset,step,call_offset,put_offset)
        if outcomes.empty:
            st.warning('No completed trades found. Provide multiple complete sessions of 3-minute candles covering the chosen window.')
        else:
            rows=[]
            for label,sub in [('All',outcomes),('Calls',outcomes[outcomes.Type=='Sell Call']),('Puts',outcomes[outcomes.Type=='Sell Put']),('ICs',outcomes[outcomes.Type=='Sell IC'])]:
                n=len(sub)
                ow=sub['Original win'].mean()*100 if n else None
                aw=sub['Adjusted win'].mean()*100 if n else None
                rows.append({'Type':label,'Trades':n,'Original win %':round(ow,2) if n else None,'Adjusted win %':round(aw,2) if n else None,'Delta pp':round(aw-ow,2) if n else None})
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
            with st.expander('Individual trades'):
                st.dataframe(outcomes,hide_index=True,use_container_width=True)
            st.download_button('Download backtest trades',outcomes.to_csv(index=False),'backtest_results.csv','text/csv')
    except Exception as e:
        st.error(f'CSV/backtest error: {e}')
st.caption('Win = settlement beyond sold strike(s), strictly. Ignores premium, fees, gaps, intraday stops and option expiry. Intraday exits use the next trading session’s same window-end boundary; daily exits use the next session’s final close. Complete 3-minute bars are required.')
