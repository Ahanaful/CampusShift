"""Repository + read-only AWS inventory, 2026-11-13. See README.md for evidence.
Run with diagrams==0.25.1 and Graphviz installed. No AWS calls are made here.
"""
from pathlib import Path
import base64
import re
from diagrams import Diagram, Cluster, Edge, Node
from diagrams.aws.compute import EC2
from diagrams.aws.network import InternetGateway
from diagrams.aws.storage import EBS

OUT = Path(__file__).resolve().parent
NAVY, TEAL = '#142D4E', '#007F86'

def box(label, **kw):
    return Node(label, shape='box', style='rounded,filled', fillcolor='white',
                color=TEAL, width='2.9', height='1.15', labelloc='c', **kw)

with Diagram('CampusShift | Deployed AWS Architecture',
             filename=str(OUT / 'campusshift-architecture'), outformat=['png','svg'],
             show=False, direction='LR',
             graph_attr={'fontname':'Helvetica','fontsize':'30','fontcolor':NAVY,
                         'bgcolor':'white','pad':'0.45','nodesep':'0.7','ranksep':'0.85',
                         'splines':'spline','dpi':'300','labelloc':'t','labeljust':'l'},
             node_attr={'fontname':'Helvetica','fontsize':'17','fontcolor':NAVY},
             edge_attr={'fontname':'Helvetica','fontsize':'14','color':TEAL,
                        'fontcolor':NAVY,'penwidth':'2','arrowsize':'0.8'}) as diagram:
    browser = box('Students & supervisors\nWeb browser')
    with Cluster('AWS Cloud  |  us-east-2 (Ohio)',
                 graph_attr={'bgcolor':'#F4F8FC','color':NAVY,'fontcolor':NAVY,'fontsize':'23','margin':'28'}):
        with Cluster('Default VPC  |  172.31.0.0/16',
                     graph_attr={'bgcolor':'white','color':'#7793AC','fontsize':'20','margin':'24'}):
            gateway = InternetGateway('Internet Gateway\nPublic IPv4 routing')
            with Cluster('Public subnet  |  172.31.0.0/20  |  us-east-2a',
                         graph_attr={'bgcolor':'#EFF9F9','color':TEAL,'fontsize':'19','margin':'24'}):
                with Cluster('Amazon EC2  |  CampusShift-Server\nSecurity group: public TCP 80 / 443; SSH from one /32',
                             graph_attr={'bgcolor':'white','color':NAVY,'fontsize':'19','margin':'25'}):
                    host = EC2('t3.micro  |  running\n3.133.115.154')
                    nginx = box('Nginx\nStatic files + reverse proxy')
                    frontend = box('React / Vite frontend\nBuilt SPA assets')
                    backend = box('FastAPI / Uvicorn\nsystemd  |  127.0.0.1:8000')
                    database = Node('SQLite database\nLocal file via SQLAlchemy',shape='cylinder',style='filled',fillcolor='white',color=TEAL,width='2.9',height='1.15',labelloc='c')
                    host >> Edge(style='dashed',label='hosts',color='#7793AC') >> nginx
                    nginx >> Edge(label='/  static assets',dir='both') >> frontend
                    nginx >> Edge(label='/api/*  HTTP + JSON',dir='both') >> backend
                    backend >> Edge(label='SQL reads / writes',dir='both') >> database
                disk = EBS('Amazon EBS  |  20 GiB gp3\nAttached root volume')
                database >> Edge(style='dashed',label='local storage',color='#7793AC') >> disk
    browser >> Edge(label='HTTPS :443\nrequests / responses',dir='both') >> gateway
    gateway >> Edge(label='Public IPv4',dir='both') >> host
    diagram.dot.attr(label='CampusShift | Deployed AWS Architecture\n\nVerified by AWS CLI, SSH and trusted HTTPS: 13 Nov 2026\nDaily SQLite snapshots; encrypted off-server copies; API health and readiness verified.',fontsize='24')
# Embed icon bytes so the SVG is portable outside the Python environment.
svg=OUT/'campusshift-architecture.svg'
text=svg.read_text()
def embed(match):
    p=Path(match.group(1))
    return 'xlink:href="data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()+'"' if p.is_file() else match.group(0)
svg.write_text(re.sub(r'xlink:href="([^"]+\.png)"',embed,text))
