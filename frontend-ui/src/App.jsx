import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Bell,
  CalendarDays,
  Check,
  ChevronRight,
  ClipboardList,
  Clock3,
  LayoutDashboard,
  Menu,
  MoreHorizontal,
  Search,
  Settings,
  ShieldCheck,
  Stethoscope,
  Users,
  X,
} from "lucide-react";

const PATIENTS = [
  { id: "rahul", name: "Rahul Kumar", initials: "RK", procedure: "Colonoscopy", time: "Tomorrow, 8:00 AM", physician: "Dr. Sharma", suite: "Endo Suite 2", status: "risk", step: "Take second prep dose", stepTime: "02:00" },
  { id: "priya", name: "Priya Nair", initials: "PN", procedure: "Colonoscopy", time: "Today, 8:30 PM", physician: "Dr. Sharma", suite: "Endo Suite 1", status: "risk", step: "Take second prep dose", stepTime: "18:30" },
  { id: "ananya", name: "Ananya Sharma", initials: "AS", procedure: "Colonoscopy", time: "Today, 7:00 PM", physician: "Dr. Sharma", suite: "Endo Suite 1", status: "ready" },
  { id: "arjun", name: "Arjun Mehta", initials: "AM", procedure: "Upper GI Endoscopy", time: "Fri, 10:30 AM", physician: "Dr. Iyer", suite: "Endo Suite 3", status: "pending" },
];

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Patient details", icon: Users },
  { label: "Procedure timeline", icon: Clock3 },
  { label: "Protocols", icon: ClipboardList },
];

function StatusBadge({ status }) {
  const styles = {
    ready: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    pending: "bg-amber-50 text-amber-700 ring-amber-100",
    risk: "bg-rose-50 text-rose-700 ring-rose-100",
  };
  const labels = { ready: "Ready", pending: "Pending", risk: "At risk" };
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${styles[status]}`}><span className={`h-1.5 w-1.5 rounded-full ${status === "ready" ? "bg-emerald-500" : status === "risk" ? "bg-rose-500" : "bg-amber-500"}`} />{labels[status]}</span>;
}

function Sidebar({ active, onNavigate, open, onClose }) {
  return (
    <>
      {open && <button aria-label="Close navigation" className="fixed inset-0 z-30 bg-slate-950/30 lg:hidden" onClick={onClose} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[254px] flex-col border-r border-line bg-white px-4 py-5 transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center justify-between px-3">
          <div className="flex items-center gap-2.5">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-brand text-white"><Stethoscope size={19} strokeWidth={2.5} /></div>
            <div><div className="text-[17px] font-bold tracking-tight text-ink">PrepBuddy</div><div className="text-[9px] font-bold uppercase tracking-[0.16em] text-brand">Clinical</div></div>
          </div>
          <button className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-50 lg:hidden" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="mt-10 space-y-1">
          <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400">Workspace</p>
          {navItems.map(({ label, icon: Icon }) => <button key={label} onClick={() => { onNavigate(label); onClose(); }} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${active === label ? "bg-brand-soft text-brand" : "text-slate-500 hover:bg-slate-50 hover:text-ink"}`}><Icon size={18} strokeWidth={active === label ? 2.3 : 1.9} />{label}{active === label && <ChevronRight size={15} className="ml-auto" />}</button>)}
        </div>
        <div className="mt-auto space-y-1">
          <button className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-500 hover:bg-slate-50 hover:text-ink"><Settings size={18} />Settings</button>
          <div className="mt-4 flex items-center gap-3 border-t border-line px-3 pt-4">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-[#f1e6ff] text-xs font-bold text-[#7b43b2]">DS</div>
            <div className="min-w-0"><p className="truncate text-sm font-semibold text-ink">Dr. Sharma</p><p className="truncate text-xs text-muted">Lead gastroenterologist</p></div>
            <MoreHorizontal size={17} className="ml-auto text-slate-400" />
          </div>
        </div>
      </aside>
    </>
  );
}

function StatCard({ label, value, description, tone, icon: Icon }) {
  return <div className="card flex min-h-[124px] flex-col justify-between p-5"><div className="flex items-start justify-between"><span className="eyebrow">{label}</span><span className={`rounded-lg p-2 ${tone}`}><Icon size={16} /></span></div><div className="flex items-end justify-between"><strong className="text-[30px] font-semibold tracking-tight text-ink">{value}</strong><span className="pb-1 text-xs text-muted">{description}</span></div></div>;
}

function Dashboard({ onToast }) {
  const [search, setSearch] = useState("");
  const filtered = useMemo(() => PATIENTS.filter((patient) => `${patient.name} ${patient.id} ${patient.procedure} ${patient.physician}`.toLowerCase().includes(search.toLowerCase())), [search]);
  const atRisk = filtered.filter((p) => p.status === "risk");
  return <div className="space-y-7">
    <div><p className="mb-2 text-xs font-medium text-slate-400">Overview / Today</p><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><h1 className="text-[28px] font-semibold tracking-tight text-ink">Clinical dashboard</h1><p className="mt-1 text-sm text-muted">Real-time tracking of patient pre-procedure compliance.</p></div><div className="flex items-center gap-2 text-xs text-muted"><span className="h-2 w-2 rounded-full bg-emerald-500" />Last synced just now</div></div></div>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><StatCard label="Procedures" value={PATIENTS.length} description="Active pipeline" tone="bg-indigo-50 text-brand" icon={CalendarDays} /><StatCard label="Ready" value={PATIENTS.filter((p) => p.status === "ready").length} description="All steps verified" tone="bg-emerald-50 text-emerald-600" icon={ShieldCheck} /><StatCard label="Pending" value={PATIENTS.filter((p) => p.status === "pending").length} description="Upcoming windows" tone="bg-amber-50 text-amber-600" icon={Clock3} /><StatCard label="At risk" value={PATIENTS.filter((p) => p.status === "risk").length} description="Action required" tone="bg-rose-50 text-rose-600" icon={AlertTriangle} /></div>
    <section className="card overflow-hidden"><div className="flex flex-col justify-between gap-4 border-b border-line px-5 py-5 sm:flex-row sm:items-center"><div><div className="flex items-center gap-2"><span className="grid h-7 w-7 place-items-center rounded-lg bg-rose-50 text-rose-600"><AlertTriangle size={15} /></span><h2 className="text-sm font-bold uppercase tracking-[0.08em] text-ink">At risk preparations</h2></div><p className="mt-2 text-xs text-muted">Patients with missed confirmation windows. Intervention advised.</p></div><span className="w-fit rounded-full bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700">{atRisk.length} urgent cases</span></div>{atRisk.length ? <div className="divide-y divide-line">{atRisk.map((patient) => <div key={patient.id} className="grid gap-4 px-5 py-4 lg:grid-cols-[1.3fr_1fr_1.3fr_1fr_auto] lg:items-center"><div className="flex items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-full bg-[#f1e6ff] text-xs font-bold text-[#7b43b2]">{patient.initials}</div><div><p className="text-sm font-semibold text-ink">{patient.name}</p><p className="text-xs text-muted">ID: {patient.id.toUpperCase()}</p></div></div><p className="text-sm text-slate-600">{patient.procedure}</p><div><span className="inline-flex rounded-md bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700">{patient.step}</span></div><div><p className="text-sm font-medium text-ink">{patient.stepTime}</p><p className="text-[11px] font-semibold uppercase tracking-wide text-rose-600">Overdue</p></div><div className="flex gap-2 lg:justify-end"><button onClick={() => onToast(`Reminder sent to ${patient.name}`)} className="rounded-lg border border-line px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50">Nudge</button><button onClick={() => onToast(`${patient.step} verified for ${patient.name}`)} className="rounded-lg bg-brand px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#4454c6]">Verify</button></div></div>)}</div> : <div className="px-5 py-8 text-center text-sm text-emerald-700">All preparation windows are on track.</div>}</section>
    <section className="card overflow-hidden"><div className="flex flex-col justify-between gap-4 border-b border-line px-5 py-5 sm:flex-row sm:items-center"><div><h2 className="text-base font-semibold text-ink">Upcoming procedures</h2><p className="mt-1 text-xs text-muted">Live operational roster and preparation clearance status.</p></div><div className="relative w-full sm:w-64"><Search size={16} className="absolute left-3 top-2.5 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Filter patients..." className="h-9 w-full rounded-lg border border-line bg-slate-50 pl-9 pr-3 text-xs outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10" /></div></div><div className="hidden grid-cols-[1.4fr_1.2fr_1fr_0.8fr_auto] gap-4 bg-slate-50/70 px-5 py-3 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400 md:grid"><span>Patient</span><span>Procedure</span><span>Date / time</span><span>Status</span><span /></div><div className="divide-y divide-line">{filtered.map((patient) => <div key={patient.id} className="grid gap-3 px-5 py-4 md:grid-cols-[1.4fr_1.2fr_1fr_0.8fr_auto] md:items-center"><div className="flex items-center gap-3"><div className={`grid h-9 w-9 place-items-center rounded-full text-xs font-bold ${patient.status === "risk" ? "bg-rose-50 text-rose-600" : patient.status === "ready" ? "bg-emerald-50 text-emerald-600" : "bg-indigo-50 text-brand"}`}>{patient.initials}</div><div><p className="text-sm font-semibold text-ink">{patient.name}</p><p className="text-xs text-muted">{patient.physician} · {patient.suite}</p></div></div><div><p className="text-sm font-medium text-slate-700">{patient.procedure}</p><p className="text-xs text-muted md:hidden">{patient.time}</p></div><p className="hidden text-sm text-slate-600 md:block">{patient.time}</p><div><StatusBadge status={patient.status} /></div><button onClick={() => onToast(`Opening timeline for ${patient.name}`)} className="flex items-center gap-1 text-left text-xs font-semibold text-brand hover:text-[#3f4ebd]">Timeline <ChevronRight size={14} /></button></div>)}</div>{filtered.length === 0 && <div className="px-5 py-10 text-center text-sm text-muted">No procedures match “{search}”.</div>}</section>
  </div>;
}

export default function App() {
  const [active, setActive] = useState("Dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toast, setToast] = useState("");
  const showToast = (message) => { setToast(message); window.setTimeout(() => setToast(""), 2800); };
  return <div className="flex min-h-screen bg-[#f8fafc]"><Sidebar active={active} onNavigate={(page) => { setActive(page); if (page !== "Dashboard") showToast(`${page} view is ready to connect to your workspace`); }} open={sidebarOpen} onClose={() => setSidebarOpen(false)} /><main className="min-w-0 flex-1"><header className="sticky top-0 z-20 flex h-[72px] items-center justify-between border-b border-line bg-white/90 px-5 backdrop-blur sm:px-8"><div className="flex items-center gap-3"><button aria-label="Open navigation" className="rounded-lg p-2 text-slate-500 hover:bg-slate-50 lg:hidden" onClick={() => setSidebarOpen(true)}><Menu size={21} /></button><div className="hidden text-sm font-medium text-slate-400 sm:block">Thursday, 08 October 2026</div></div><div className="flex items-center gap-3"><button aria-label="Notifications" onClick={() => showToast("You are all caught up")} className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-50"><Bell size={19} /><span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-rose-500 ring-2 ring-white" /></button><div className="hidden h-6 w-px bg-line sm:block" /><div className="grid h-8 w-8 place-items-center rounded-full bg-[#f1e6ff] text-[10px] font-bold text-[#7b43b2]">DS</div></div></header><div className="mx-auto max-w-[1440px] p-5 sm:p-8">{active === "Dashboard" ? <Dashboard onToast={showToast} /> : <div className="card grid min-h-[420px] place-items-center p-8 text-center"><div><div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-brand-soft text-brand"><ClipboardList size={24} /></div><h1 className="text-xl font-semibold text-ink">{active}</h1><p className="mt-2 max-w-sm text-sm text-muted">This workspace is ready for your Django API integration.</p></div></div>}</div></main>{toast && <div role="status" className="fixed bottom-5 right-5 z-50 flex items-center gap-3 rounded-xl bg-ink px-4 py-3 text-sm font-medium text-white shadow-xl"><Check size={17} className="text-emerald-400" />{toast}</div>}</div>;
}
