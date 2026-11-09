from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color, white, black
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
F='/usr/share/fonts/truetype/sand-box/google/Carlito/'
pdfmetrics.registerFont(TTFont('Carlito',F+'Carlito-Regular.ttf'))
pdfmetrics.registerFont(TTFont('Carlito-Bold',F+'Carlito-Bold.ttf'))
OUT='/workspace/website-guru/ideamille rebuild v2 2026-10-30/assets/forms/IdeaMille North Carolina Idea Form.pdf'
import os; os.makedirs(os.path.dirname(OUT),exist_ok=True)
G=Color(146/255,208/255,80/255); LBL=Color(0x2E/255,0x6B/255,0x1F/255); LBLS=Color(0x1F/255,0x4A/255,0x15/255); TG=Color(0x14/255,0x50/255,0x0F/255)
c=canvas.Canvas(OUT,pagesize=(720,540))
c.setTitle('North Carolina ideaMille: 1000 ideas driving our future - Idea Form')
c.setAuthor('IdeaMille / TechVest Ventures'); c.setSubject('Fillable idea submission form - send to ideas@techvestventures.com')
c.setFillColor(G); c.rect(0,0,720,540,stroke=0,fill=1)
c.setFillColor(white)
rects=[(30.2,468,689.8,504),(36,300.2,347.8,426.2),(383.8,383.8,689.8,426.2),(383.8,306,689.8,347.8),(383.8,257.8,689.8,300.2),
(36,210.2,347.8,252),(36,102.2,347.8,203.8)]+[(383.8,y,689.8,y+18) for y in (192.2,167.8,144,120.2,95.8,72,48.2)]
for x0,y0,x1,y1 in rects: c.rect(x0,y0,x1-x0,y1-y0,stroke=0,fill=1)
# title with soft shadow
def shadow_text(x,y,t,size,align='left'):
    c.setFont('Carlito-Bold',size)
    w=c.stringWidth(t,'Carlito-Bold',size)
    if align=='right': x=x-w
    c.setFillColor(Color(.55,.55,.55)); c.drawString(x+1.2,y-1.2,t)
    c.setFillColor(TG); c.drawString(x,y,t)
shadow_text(44,477,'North Carolina ideaMille:',20)
shadow_text(677,477,'1000 ideas driving our future',20,'right')
c.setFillColor(black); c.setFont('Carlito',15)
for x,y,t in [(37,429,'what\u2019s your brilliant idea'),(391,429,'why is this cool'),(391,351,'how does it succeed'),(43,255,'who are you'),(391,207+4+3,'where are you'),(43,70,'send us any file <10mb')]:
    if t=='where are you': y=213.5
    c.drawString(x,y,t)
c.setFillColor(LBL); c.setStrokeColor(LBLS); c.setLineWidth(0.1); c.setFont('Carlito',11)
labels=[(43,413,'140 characters max'),(391,414,'why is this powerful'),(391,336,'how does it make money'),(391,288,'problems solved'),(43,240,'name(s)'),(43,192,'bio(s)')]
small=['name','phone','location','e-mail','zoom / video link','linkedin','website']
ys=[192.2,167.8,144,120.2,95.8,72,48.2]
def ol(x,y,t,centre=False):
    o=c.beginText(); o.setTextRenderMode(2); o.setFont(c._fontname,c._fontsize)
    if centre: x=x-c.stringWidth(t,c._fontname,c._fontsize)/2
    o.setTextOrigin(x,y); o.textOut(t); o.setTextRenderMode(0); c.drawText(o)
for (x,y,t) in labels: ol(x,y,t)
for t,y in zip(small,ys): ol(391,y+5,t)
# attach "button"
c.setFillColor(white); c.setStrokeColor(black); c.setLineWidth(.75)
c.roundRect(42.5,42.5,150,23,3,stroke=1,fill=1)
c.setFillColor(LBL); c.setStrokeColor(LBLS); c.setLineWidth(0.1); c.setFont('Carlito',12.5); ol(117.5,50.5,'attach it to your e-mail',True); c.setStrokeColor(black); c.setLineWidth(.75)
c.setFont('Carlito',9.5); c.setFillColor(Color(.15,.35,.1))
c.drawString(43,28,'Save this form and e-mail it (plus any file) to ideas@techvestventures.com')
c.linkURL('mailto:ideas@techvestventures.com',(43,25,360,38),relative=0)
# fields
f=c.acroForm
def fld(name,x0,y0,x1,y1,multi,tip):
    f.textfield(name=name,tooltip=tip,x=x0,y=y0,width=min(x1,347.8 if x0<360 else 689.8)-x0,height=y1-y0,borderWidth=0,borderColor=None,fillColor=white,
        textColor=black,forceBorder=False,fontName='Helvetica',fontSize=10 if multi else 0,fieldFlags='multiline' if multi else '')
def lw(t): return c.stringWidth(t,'Carlito',11)
F13=[('140_characters_max',36,300,349,405,1,'Your brilliant idea (140 characters max)'),
('why_is_this_powerful',384,384,690,407,1,'Why is this powerful'),
('how_does_it_make_money',384,306,690,329,1,'How does it make money'),
('problems_solved',384,258,690,281,1,'Problems solved'),
('names',88,210,349,250,1,'Name(s)'),('bios',36,102,349,182,1,'Bio(s)')]
for i,(lab,nm) in enumerate(zip(small,['name','phone','location','email','zoom','linkedin','website'])):
    y=ys[i]; F13.append((nm,round(391+lw(lab)+6),y,690,y+18,0,lab))
for a in F13: fld(*a)
c.showPage(); c.save(); print('ok',OUT)
