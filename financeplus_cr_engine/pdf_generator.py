from __future__ import annotations
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from .models import Analysis
NAVY=HexColor('#102A43'); CYAN=HexColor('#27B6C7'); ORANGE=HexColor('#F59E42'); RED=HexColor('#E95A67'); PURPLE=HexColor('#9461D9'); GREEN=HexColor('#2EB67D'); LIGHT=HexColor('#F3F5F7'); GREY=HexColor('#6B7280')
PAGES=[('COPERTINA','Analisi CR avanzata'),('INDICE','Struttura completa del report avanzato a 36 mesi'),('SEZIONE 1','Scoring e ranking'),('1.01 SCORING CENTRALE RISCHI','Giudizio di sintesi'),('1.02 / 1.03 MONTE AFFIDAMENTI / UTILIZZI','Ultimo mese per forma tecnica'),('1.04 / 1.05 INFORMAZIONI QUANTITATIVE / DISTINTA BANCHE','Quadro sintetico'),('1.06 DISTINTA BANCHE - ULTIMI 36 MESI','Andamento aggregato'),('1.06 DISTINTA BANCHE - CONTINUAZIONE','Seconda parte della serie storica'),('MONITORAGGIO FATTORI DI RISCHIO','Ultimi 6 mesi'),('ANALISI COMPORTAMENTALE - RANKING BANCHE','Top per grandezza'),('1.07 RANKING BANCHE PER ACCORDATO OPERATIVO','Ultimo mese'),('1.08 RANKING BANCHE PER UTILIZZATO','Ultimo mese'),('1.09 RANKING BANCHE PER SCONFINI','Ultimo mese e cumulato'),('1.10 RANKING GARANZIE','Ultimo mese'),('SEZIONE 2','Eventi negativi'),('2.01 CREDITI PASSATI A PERDITA E SOFFERENZE','Ultimi 36 mesi'),('2.02 / 2.03 CREDITI SCADUTI E SCONFINATI 90/180 GG','Durata anomalie'),('2.04 / 2.05 SCONFINI EVITABILI E COMPENSAZIONI','Capienza disponibile'),('2.06 / 2.07 SCONFINI PER BANCA ED EVENTI NEGATIVI','Dettaglio istituto'),('2.08 SCONFINI INFRAMENSILI','Stima prudenziale'),('SEZIONE 3','Garanzie'),('3.01 GARANZIE PRESTATE SU PROPRI AFFIDAMENTI','Valore e copertura'),('3.02 / 3.03 GARANZIE DI TERZI E COINTESTAZIONI','Posizioni collegate'),('3.04 DATI MCC - MEDIO CREDITO CENTRALE','Indicatori andamentali'),('3.05 / 3.06 ANDAMENTO DERIVATI','Prima parte'),('3.06 DERIVATI - CONTINUAZIONE','Seconda parte'),('SEZIONE 4','Tesoreria'),('4.01 TASSI APPLICATI ALLE IMPRESE','Benchmark e avvertenze'),('4.02 FABBISOGNO TESORERIA','Proiezione a 6 mesi'),('4.03 DISPONIBILITA FIDI A REVOCA','Media fino a 36 mesi'),('4.04 ANALISI ONERI FINANZIARI','Sottoutilizzo e commissioni'),('4.05 EQUILIBRIO DI TESORERIA','Utilizzo medio'),('4.06 PORTAFOGLIO EFFETTI E POLMONE FINANZIARIO','Capacita di assorbimento'),('4.07 IMPATTO IMPAGATI DELLA CLIENTELA','Confronto con revoca'),('SEZIONE 5','Altre linee e segnalazioni'),('5.01 / 5.02 RICHIESTE DI INFORMAZIONI E CONTESTAZIONI','Ultimi 6 mesi'),('5.03 RETTIFICHE','Variazioni alle segnalazioni'),('5.04 FACTORING ATTIVI E CESSIONE DI CREDITO','Soggetto cedente'),('5.05 FACTORING PASSIVI E CESSIONE DI CREDITO','Debitore ceduto'),('5.06 CREDITI DI FIRMA','Natura commerciale e finanziaria'),('5.07 LEASING','Peso sulle linee a scadenza'),('5.08 IMPORT / EXPORT / DIVISA','Crediti per cassa e firma'),('5.09 OPERAZIONI PER CONTO TERZI','Riepilogo'),('5.10 RIEPILOGO GENERALE PER BANCA','Quadro conclusivo'),('AVVERTENZE METODOLOGICHE','Controlli e limiti del report')]
def _money(v):return f"EUR {v:,.0f}".replace(',','.')
def _footer(c,n):
 c.setStrokeColor(HexColor('#E5E7EB'));c.line(15*mm,14*mm,195*mm,14*mm);c.setFont('Helvetica-Bold',7);c.setFillColor(NAVY);c.drawCentredString(105*mm,8*mm,'www.financeplus.tech');c.setFont('Helvetica',7);c.setFillColor(GREY);c.drawRightString(195*mm,8*mm,f'Pagina {n} di 45')
def _title(c,title,sub,color=CYAN):
 c.setFillColor(NAVY);c.setFont('Helvetica-Bold',18);c.drawString(15*mm,280*mm,title[:70]);c.setStrokeColor(color);c.setLineWidth(2);c.line(15*mm,274*mm,195*mm,274*mm);c.setFont('Helvetica',9);c.setFillColor(GREY);c.drawString(15*mm,267*mm,sub[:110])
def _card(c,x,y,w,label,value,color):
 c.setFillColor(LIGHT);c.roundRect(x,y,w,20*mm,4*mm,fill=1,stroke=0);c.setFillColor(color);c.rect(x,y,1.5*mm,20*mm,fill=1,stroke=0);c.setFillColor(GREY);c.setFont('Helvetica',6.5);c.drawString(x+4*mm,y+14*mm,label);c.setFillColor(NAVY);c.setFont('Helvetica-Bold',12);c.drawString(x+4*mm,y+5*mm,str(value)[:24])
def _table(c,headers,rows,y=230*mm,widths=None,maxrows=12):
 rows=rows[:maxrows];x=15*mm;total=180*mm;widths=widths or [total/len(headers)]*len(headers);h=8*mm;c.setFillColor(NAVY);c.rect(x,y,total,h,fill=1,stroke=0);c.setFillColor(white);c.setFont('Helvetica-Bold',6);xx=x
 for hd,w in zip(headers,widths):c.drawString(xx+2*mm,y+2.5*mm,str(hd)[:28]);xx+=w
 for i,row in enumerate(rows):
  yy=y-(i+1)*h;c.setFillColor(white if i%2 else HexColor('#F8FAFC'));c.rect(x,yy,total,h,fill=1,stroke=0);c.setFillColor(NAVY);c.setFont('Helvetica',6);xx=x
  for val,w in zip(row,widths):c.drawString(xx+2*mm,yy+2.5*mm,str(val)[:32]);xx+=w
 if not rows:c.setFillColor(LIGHT);c.roundRect(x,y-24*mm,total,16*mm,3*mm,fill=1,stroke=0);c.setFillColor(GREY);c.setFont('Helvetica-Bold',11);c.drawCentredString(105*mm,y-15*mm,'nessun dato presente')
def _latest(a):return a.monthly[-1] if a.monthly else {'operating_accorded':0,'used':0,'overrun':0,'guaranteed':0,'saturation':None,'banks':0}
def generate_pdf(a:Analysis,output:str|Path,allow_invalid=False):
 if not a.audit.valid and not allow_invalid:raise ValueError('Controllo di congruita non superato: '+'; '.join(a.audit.errors))
 c=canvas.Canvas(str(output),pagesize=A4);latest=_latest(a)
 for n,(title,sub) in enumerate(PAGES,1):
  if title=='COPERTINA':c.setFillColor(NAVY);c.rect(0,0,*A4,fill=1,stroke=0);c.setFillColor(white);c.setFont('Helvetica-Bold',30);c.drawString(20*mm,235*mm,'ANALISI');c.drawString(20*mm,220*mm,'CR');c.drawString(20*mm,205*mm,'AVANZATA');c.setFont('Helvetica-Bold',18);c.drawString(20*mm,160*mm,a.subject[:45]);c.setFont('Helvetica',11);c.drawString(20*mm,145*mm,'periodo censito');c.drawString(20*mm,137*mm,(a.periods[0]+' - '+a.periods[-1]) if a.periods else 'nessun dato presente')
  elif title.startswith('SEZIONE'):c.setFillColor(NAVY);c.rect(0,0,*A4,fill=1,stroke=0);c.setFillColor(white);c.setFont('Helvetica-Bold',24);c.drawString(20*mm,220*mm,sub.upper());c.setFont('Helvetica',12);c.drawString(20*mm,200*mm,a.subject[:60])
  elif title=='INDICE':
   _title(c,title,sub);c.setFont('Helvetica',8);c.setFillColor(NAVY);y=255*mm
   for i,(t,s) in enumerate(PAGES[2:],3):
    c.drawString(18*mm,y,f'{i:02d}  {t[:58]}');y-=5.5*mm
    if y<25*mm:break
  else:
   color=RED if title.startswith('2.') else PURPLE if title.startswith('3.') else ORANGE if title.startswith('4.') else GREEN if title.startswith('5.') else CYAN;_title(c,title,sub,color)
   if n==4:_card(c,15*mm,235*mm,40*mm,'SCORE',f'{a.score}/100',CYAN);_card(c,60*mm,235*mm,40*mm,'RATING',a.rating,GREEN);_card(c,105*mm,235*mm,40*mm,'PD STIMATA',f'{a.pd:.2f}%',ORANGE);_card(c,150*mm,235*mm,40*mm,'ESITO AUDIT','OK' if a.audit.valid else 'BLOCCATO',PURPLE);_table(c,['ANOMALIE','ESITO'],[(x,'SI') for x in a.anomalies],205*mm,[140*mm,40*mm])
   elif n in (5,6):_card(c,15*mm,235*mm,40*mm,'AFFIDAMENTI',_money(latest['operating_accorded']),CYAN);_card(c,60*mm,235*mm,40*mm,'UTILIZZI',_money(latest['used']),ORANGE);_card(c,105*mm,235*mm,40*mm,'SCONFINI',_money(latest['overrun']),RED);_card(c,150*mm,235*mm,40*mm,'ISTITUTI',latest['banks'],GREEN);_table(c,['BANCA','UTILIZZATO','PESO'],[(x['intermediary'],_money(x['value']),f"{x['weight']:.1f}%") for x in a.bank_ranking['used']],205*mm,[110*mm,40*mm,30*mm])
   elif n in (7,8,28,29,30,31,32,33,34):_table(c,['PERIODO','ACCORDATO OP.','UTILIZZATO','SCONFINI','SATURAZIONE'],[(m['period'],_money(m['operating_accorded']),_money(m['used']),_money(m['overrun']),('n.d.' if m['saturation'] is None else f"{m['saturation']:.1f}%")) for m in a.monthly],245*mm,[28*mm,42*mm,42*mm,35*mm,33*mm])
   elif n in (10,11,12,13,14):
    key={11:'operating_accorded',12:'used',13:'overrun',14:'guaranteed'}.get(n,'used');_table(c,['BANCA','IMPORTO','PESO'],[(x['intermediary'],_money(x['value']),f"{x['weight']:.1f}%") for x in a.bank_ranking[key]],245*mm,[115*mm,40*mm,25*mm])
   elif n in (22,23):_table(c,['BANCA','GARANTE / COINTESTAZIONE','VALORE','GARANTITO'],[(g.get('intermediary',''),g.get('guarantor',''),_money(g.get('value',0)),_money(g.get('guaranteed_amount',0))) for g in a.guarantees],245*mm,[55*mm,70*mm,28*mm,27*mm])
   elif n==24:_card(c,15*mm,235*mm,40*mm,'CR SCORE',f'{a.score}/100',CYAN);_card(c,60*mm,235*mm,40*mm,'RATING',a.rating,GREEN);_card(c,105*mm,235*mm,40*mm,'PD',f'{a.pd:.2f}%',ORANGE);_card(c,150*mm,235*mm,40*mm,'GARANZIE',_money(latest['guaranteed']),PURPLE);_table(c,['PERIODO','ACCORDATO OP.','UTILIZZATO','SCONFINI'],[(m['period'],_money(m['operating_accorded']),_money(m['used']),_money(m['overrun'])) for m in a.monthly[-6:]],205*mm,[35*mm,50*mm,50*mm,45*mm])
   elif n==36:_table(c,['INTERMEDIARIO','DATA','PERIODO','CAUSALE'],[(r.get('intermediary',''),r.get('request_date',''),r.get('requested_period',''),r.get('reason','')) for r in a.info_requests],245*mm,[55*mm,25*mm,35*mm,65*mm])
   elif n==37:_table(c,['PERIODO','INTERMEDIARIO','DESCRIZIONE'],[(r.get('period',''),r.get('intermediary',''),r.get('description','')) for r in a.corrections],245*mm,[30*mm,65*mm,85*mm])
   elif n==44:
    rows=[]
    for key in ('operating_accorded','used','overrun','guaranteed'):
     for x in a.bank_ranking[key]:rows.append((x['intermediary'],key,_money(x['value'])))
    _table(c,['BANCA','INDICATORE','IMPORTO'],rows,245*mm,[95*mm,45*mm,40*mm])
   elif n==45:_table(c,['CONTROLLO','ESITO'],[(e,'ERRORE') for e in a.audit.errors]+[(w,'AVVISO') for w in a.audit.warnings],245*mm,[145*mm,35*mm])
   else:
    relevant=[]
    if title.startswith('2.') and latest['overrun']>0:relevant=[('Sconfini ultimo mese',_money(latest['overrun']))]
    if title.startswith('3.') and a.guarantees:relevant=[('Garanzie rilevate',str(len(a.guarantees)))]
    _table(c,['INDICATORE','VALORE'],relevant,245*mm,[125*mm,55*mm])
  _footer(c,n);c.showPage()
 c.save();return Path(output)
