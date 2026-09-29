"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Activity, Building2, ChevronDown, FileText, LayoutDashboard, LogIn, Menu, Settings, Users, WalletCards, X } from "lucide-react";
const links = [{href:"/",label:"Overview",icon:LayoutDashboard},{href:"/invoices",label:"Invoices",icon:FileText},{href:"/banking",label:"Banking",icon:WalletCards},{href:"/customers",label:"Customers",icon:Users},{href:"/suppliers",label:"Suppliers",icon:Building2},{href:"/audit",label:"Activity",icon:Activity}];
export function AppShell({children}:{children:React.ReactNode}) {
 const path=usePathname(); const [open,setOpen]=useState(false);
 return <div className="app-frame"><button className="mobile-menu" onClick={()=>setOpen(!open)} aria-label={open?"Close navigation":"Open navigation"}>{open?<X size={19}/>:<Menu size={19}/>}</button>{open&&<button className="scrim" aria-label="Close navigation" onClick={()=>setOpen(false)}/>}
 <aside className={`sidebar ${open?"sidebar-open":""}`}><Link className="brand" href="/"><span className="brand-mark">O</span><span>OpenInvoice</span></Link><button className="workspace"><span className="workspace-icon">N</span><span className="workspace-name">Northstar Studio<small>Workspace</small></span><ChevronDown size={15}/></button>
 <div className="nav-caption">WORKSPACE</div><nav aria-label="Main navigation">{links.map(({href,label,icon:Icon})=><Link key={href} href={href} onClick={()=>setOpen(false)} className={`nav-link ${path===href||path.startsWith(href+"/")&&href!=="/"?"active":""}`}><Icon size={17}/>{label}{label==="Invoices"&&<span className="nav-count">8</span>}</Link>)}</nav>
 <div className="sidebar-bottom"><Link href="/settings" className={`nav-link ${path==="/settings"?"active":""}`}><Settings size={17}/>Settings</Link><Link href="/auth" className={`nav-link ${path==="/auth"?"active":""}`}><LogIn size={17}/>Sign in / switch account</Link><div className="profile"><span className="avatar">OI</span><span>OpenInvoice<small>Self-hosted workspace</small></span></div></div></aside>
 <main className="main-area">{children}</main></div>;
}
