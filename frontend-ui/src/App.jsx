import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Patient details", icon: Users },
  { label: "Procedure timeline", icon: Clock3 },
  { label: "Protocols", icon: ClipboardList },
];

function StatusBadge({ status }) {
  const config = {
    ready: {
      label: "Ready",
      style: "bg-emerald-50 text-emerald-700 ring-emerald-100",
      dot: "bg-emerald-500",
    },
    scheduled: {
      label: "Scheduled",
      style: "bg-amber-50 text-amber-700 ring-amber-100",
      dot: "bg-amber-500",
    },
    prep_in_progress: {
      label: "Prep in progress",
      style: "bg-blue-50 text-blue-700 ring-blue-100",
      dot: "bg-blue-500",
    },
    attention_needed: {
      label: "Attention Needed",
      style: "bg-rose-50 text-rose-700 ring-rose-100",
      dot: "bg-rose-500",
    },
    cancelled: {
      label: "Cancelled",
      style: "bg-slate-100 text-slate-600 ring-slate-200",
      dot: "bg-slate-400",
    },
    completed: {
      label: "Completed",
      style: "bg-emerald-50 text-emerald-700 ring-emerald-100",
      dot: "bg-emerald-500",
    },
  };
  const item = config[status] ?? config.scheduled;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${item.style}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${item.dot}`} />
      {item.label}
    </span>
  );
}

function Sidebar({ active, onNavigate, open, onClose, doctor }) {
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
          <button onClick={() => { onNavigate("Settings"); onClose(); }} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${active === "Settings" ? "bg-brand-soft text-brand" : "text-slate-500 hover:bg-slate-50 hover:text-ink"}`}><Settings size={18} strokeWidth={active === "Settings" ? 2.3 : 1.9} />Settings{active === "Settings" && <ChevronRight size={15} className="ml-auto" />}</button>
          <button
            type="button"
            onClick={() => {
              onNavigate("Doctor profile");
              onClose();
            }}
            className={`mt-4 flex w-full items-center gap-3 border-t border-line px-3 pt-4 text-left ${
              active === "Doctor profile" ? "text-brand" : "text-ink"
            }`}
          >
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[#f1e6ff] text-xs font-bold text-[#7b43b2]">
              {(doctor?.name || "Doctor")
                .split(/\s+/)
                .filter(Boolean)
                .map((part) => part[0])
                .join("")
                .slice(0, 2)
                .toUpperCase()}
            </div>

            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">
                {doctor?.name || "Doctor"}
              </p>
              <p className="truncate text-xs text-muted">
                {doctor?.role || "Medical professional"}
              </p>
            </div>

            <MoreHorizontal size={17} className="shrink-0 text-slate-400" />
          </button>
        </div>
      </aside>
    </>
  );
}

function StatCard({ label, value, description, tone, icon: Icon }) {
  return <div className="card flex min-h-[124px] flex-col justify-between p-5"><div className="flex items-start justify-between"><span className="eyebrow">{label}</span><span className={`rounded-lg p-2 ${tone}`}><Icon size={16} /></span></div><div className="flex items-end justify-between"><strong className="text-[30px] font-semibold tracking-tight text-ink">{value}</strong><span className="pb-1 text-xs text-muted">{description}</span></div></div>;
}

function Dashboard({ onOpenProcedure, onToast }) {
  const [search, setSearch] = useState("");
  const [procedures, setProcedures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const controllerRef = useRef(null);
  const isMountedRef = useRef(true);
  const isFirstLoadRef = useRef(true);

  const refreshProcedures = useCallback(async (isManual = false) => {
    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      if (isFirstLoadRef.current) {
        setLoading(true);
      }
      if (isManual) {
        setRefreshing(true);
      }

      const response = await fetch(
        "http://127.0.0.1:8000/api/procedures/",
        {
          signal: controller.signal,
          cache: "no-store",
        }
      );

      if (!response.ok) {
        throw new Error(`API request failed (${response.status})`);
      }

      const result = await response.json();

      const rows = (result.procedures ?? []).map((p) => ({
        id: p.id,
        name: `${p.patient.first_name} ${p.patient.last_name}`,
        initials: `${p.patient.first_name?.[0] ?? ""}${p.patient.last_name?.[0] ?? ""}`,
        procedure: p.procedure_name,
        time: new Date(p.scheduled_at).toLocaleString(),
        status: p.status,
      }));

      if (isMountedRef.current) {
        setProcedures(rows);
        setLastUpdated(new Date());
        setError("");
      }
    } catch (err) {
      if (err.name !== "AbortError" && isMountedRef.current) {
        setError(err.message || "Unable to load procedures.");
      }
    } finally {
      if (isMountedRef.current) {
        if (isFirstLoadRef.current) {
          setLoading(false);
          isFirstLoadRef.current = false;
        }
        if (isManual) {
          setRefreshing(false);
        }
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    refreshProcedures();

    const intervalId = setInterval(() => refreshProcedures(), 10000);

    return () => {
      isMountedRef.current = false;
      controllerRef.current?.abort();
      clearInterval(intervalId);
    };
  }, [refreshProcedures]);

  const filtered = useMemo(
    () =>
      procedures.filter((p) =>
        `${p.name} ${p.id} ${p.procedure} ${p.status}`
          .toLowerCase()
          .includes(search.toLowerCase())
      ),
    [procedures, search]
  );

  const attentionNeeded = filtered.filter(
    (p) => p.status === "attention_needed"
  );
  const readyCount = procedures.filter((p) => p.status === "ready").length;
  const pendingCount = procedures.filter((p) =>
    ["scheduled", "prep_in_progress"].includes(p.status)
  ).length;

  if (loading) {
    return <div className="p-8 text-sm text-muted">Loading procedures from Django...</div>;
  }

  if (error) {
    return (
      <div className="card p-8">
        <h1 className="text-xl font-semibold text-ink">Dashboard unavailable</h1>
        <p className="mt-2 text-sm text-rose-600">{error}</p>
        <p className="mt-2 text-sm text-muted">
          Check that Django is running and that the procedures API URL is correct.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-7">
      <div>
        <p className="mb-2 text-xs font-medium text-slate-400">Overview / Procedures</p>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-[28px] font-semibold tracking-tight text-ink">Clinical dashboard</h1>
          <button
            onClick={() => refreshProcedures(true)}
            disabled={refreshing}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {refreshing ? "Refreshing..." : "Refresh data"}
          </button>
        </div>
        <p className="mt-1 text-sm text-muted">Procedure statuses loaded from PrepBuddy.</p>
        <p className="mt-1 text-sm text-muted">
          {lastUpdated
            ? `Last updated at ${lastUpdated.toLocaleTimeString()}`
            : "Waiting for data..."}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Procedures" value={procedures.length} description="Database records" tone="bg-indigo-50 text-brand" icon={CalendarDays} />
        <StatCard label="Ready" value={readyCount} description="Ready procedures" tone="bg-emerald-50 text-emerald-600" icon={ShieldCheck} />
        <StatCard label="Pending" value={pendingCount} description="Preparation ongoing" tone="bg-amber-50 text-amber-600" icon={Clock3} />
        <StatCard label="Attention Needed" value={procedures.filter((p) => p.status === "attention_needed").length} description="Action required" tone="bg-rose-50 text-rose-600" icon={AlertTriangle} />
      </div>

      {attentionNeeded.length > 0 && (
        <section className="card overflow-hidden">
          <div className="border-b border-line bg-rose-50/60 px-5 py-4">
            <div className="flex items-center gap-2 text-rose-700">
              <AlertTriangle size={18} />
              <h2 className="font-bold">Attention Needed</h2>
            </div>
            <p className="mt-1 text-xs text-rose-700">These procedures need hospital staff review.</p>
          </div>
          <div className="divide-y divide-line">
            {attentionNeeded.map((p) => (
              <div key={p.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-semibold text-ink">{p.name}</p>
                  <p className="text-sm text-muted">{p.procedure} · Procedure #{p.id}</p>
                </div>
                <StatusBadge status={p.status} />
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="card overflow-hidden">
        <div className="flex flex-col justify-between gap-4 border-b border-line px-5 py-5 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-base font-semibold text-ink">Upcoming procedures</h2>
            <p className="mt-1 text-xs text-muted">Live records returned by the Django API.</p>
          </div>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter patients..."
            className="h-9 rounded-lg border border-line bg-slate-50 px-3 text-xs outline-none focus:border-brand"
          />
        </div>
        <div className="divide-y divide-line">
          {filtered.map((p) => (
            <div
              key={p.id}
              onClick={() => {
                onToast(`Opening procedure #${p.id}`);
                onOpenProcedure(p.id);
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onToast(`Opening procedure #${p.id}`);
                  onOpenProcedure(p.id);
                }
              }}
              className="grid cursor-pointer gap-3 px-5 py-4 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand md:grid-cols-[1.4fr_1.2fr_1fr_auto] md:items-center"
            >
              <div>
                <p className="font-semibold text-ink">{p.name}</p>
                <p className="text-xs text-muted">Procedure #{p.id}</p>
              </div>
              <p className="text-sm text-slate-600">{p.procedure}</p>
              <p className="text-sm text-slate-600">{p.time}</p>
              <StatusBadge status={p.status} />
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="px-5 py-10 text-center text-sm text-muted">No procedures match your search.</div>
          )}
        </div>
      </section>
    </div>
  );
}

function PatientDetails() {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadPatients() {
      try {
        const response = await fetch(
          "http://127.0.0.1:8000/api/patients/"
        );

        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }

        const data = await response.json();

        if (!cancelled) {
          setPatients(data.patients ?? []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Could not load patients.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadPatients();

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <div className="p-8 text-sm text-muted">Loading patients...</div>;
  }

  if (error) {
    return (
      <div className="card p-8">
        <h1 className="text-xl font-semibold text-ink">Could not load patients</h1>
        <p className="mt-2 text-sm text-rose-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-7">
      <div>
        <p className="mb-2 text-xs font-medium text-slate-400">Overview / Patients</p>
        <h1 className="text-[28px] font-semibold tracking-tight text-ink">Patient details</h1>
        <p className="mt-1 text-sm text-muted">
          Patient records loaded from the PrepBuddy database.
        </p>
      </div>

      <div className="card overflow-hidden">
        <div className="border-b border-line px-5 py-4">
          <h2 className="font-semibold text-ink">
            Registered patients ({patients.length})
          </h2>
        </div>

        {patients.length === 0 ? (
          <p className="p-5 text-sm text-muted">No patients found.</p>
        ) : (
          <div className="divide-y divide-line">
            {patients.map((patient) => (
              <div key={patient.id} className="p-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h3 className="font-semibold text-ink">
                      {patient.first_name} {patient.last_name}
                    </h3>
                    <p className="mt-1 text-sm text-muted">
                      Patient ID: {patient.id}
                    </p>
                    <p className="mt-1 text-sm text-muted">
                      Phone: {patient.phone_number}
                    </p>
                    {patient.email && (
                      <p className="mt-1 text-sm text-muted">
                        Email: {patient.email}
                      </p>
                    )}
                  </div>

                  <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
                    {(patient.procedures ?? []).length} procedure(s)
                  </span>
                </div>

                {(patient.procedures ?? []).length > 0 && (
                  <div className="mt-4 space-y-3">
                    {patient.procedures.map((procedure) => (
                      <div
                        key={procedure.id}
                        className="rounded-lg border border-line bg-slate-50 p-4"
                      >
                        <p className="font-medium text-ink">
                          {procedure.procedure_name}
                        </p>
                        <p className="mt-1 text-xs text-muted">
                          Scheduled:{" "}
                          {new Date(procedure.scheduled_at).toLocaleString()}
                        </p>
                        <div className="mt-2">
                          <StatusBadge status={procedure.status} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ProcedureTimeline({ procedureId, onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  const loadTimeline = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setError("");

      const response = await fetch(
        `http://127.0.0.1:8000/api/procedures/${procedureId}/timeline/`,
        { cache: "no-store" }
      );

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const result = await response.json();
      setData(result);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message || "Unable to load timeline.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [procedureId]);

  useEffect(() => {
    loadTimeline();
  }, [loadTimeline]);

  if (loading) {
    return <div className="p-8 text-sm text-muted">Loading procedure timeline...</div>;
  }

  if (error) {
    return (
      <div className="card p-8">
        <h1 className="text-xl font-semibold text-ink">
          Could not load procedure timeline
        </h1>
        <p className="mt-2 text-sm text-rose-600">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const { procedure, timeline } = data;
  const statusStyles = {
    pending: "bg-amber-50 text-amber-700",
    sent: "bg-blue-50 text-blue-700",
    confirmed: "bg-emerald-50 text-emerald-700",
    missed: "bg-rose-50 text-rose-700",
    failed: "bg-red-100 text-red-800",
    cancelled: "bg-slate-100 text-slate-600",
  };

  function formatDate(value) {
    return value ? new Date(value).toLocaleString() : "—";
  }

  return (
    <div className="space-y-7">
      <div>
        <p className="mb-2 text-xs font-medium text-slate-400">
          Overview / Procedure timeline
        </p>
        <h1 className="text-[28px] font-semibold tracking-tight text-ink">
          Procedure timeline
        </h1>
        <div className="mt-3 flex gap-2">
          <button
            onClick={onBack}
            className="rounded-lg border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-slate-50"
          >
            Back to workspace
          </button>
          <button
            onClick={() => loadTimeline(true)}
            disabled={refreshing}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {refreshing ? "Refreshing..." : "Refresh timeline"}
          </button>
        </div>
        <p className="mt-1 text-sm text-muted">
          Preparation progress from the PrepBuddy database.
        </p>
        {lastUpdated && (
          <p className="mt-1 text-sm text-muted">
            Last updated at {lastUpdated.toLocaleTimeString()}
          </p>
        )}
      </div>

      <section className="card p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-ink">
              {procedure.procedure_name}
            </h2>
            <p className="mt-1 text-sm text-muted">
              Patient: {procedure.patient.first_name}{" "}
              {procedure.patient.last_name}
            </p>
            <p className="mt-1 text-sm text-muted">
              Scheduled: {formatDate(procedure.scheduled_at)}
            </p>
          </div>
          <StatusBadge status={procedure.status} />
        </div>
      </section>

      <section className="card p-5 sm:p-6">
        <h2 className="text-lg font-semibold text-ink">
          Preparation steps ({timeline.length})
        </h2>

        <div className="mt-6 space-y-6">
          {timeline.map((step, index) => {
            const reminder = step.reminder;
            const status = reminder?.status;
            const statusClass =
              statusStyles[status] ?? "bg-slate-100 text-slate-600";

            return (
              <div key={step.step_id} className="relative flex gap-4">
                <div className="flex flex-col items-center">
                  <div
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                      status === "confirmed"
                        ? "bg-emerald-100 text-emerald-700"
                        : status === "missed"
                        ? "bg-rose-100 text-rose-700"
                        : "bg-indigo-50 text-indigo-700"
                    }`}
                  >
                    {index + 1}
                  </div>
                  {index < timeline.length - 1 && (
                    <div className="mt-2 w-px flex-1 bg-slate-200" />
                  )}
                </div>

                <div className="min-w-0 flex-1 rounded-xl border border-line p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <h3 className="font-semibold text-ink">{step.title}</h3>
                    {step.is_critical && (
                      <span className="rounded-full bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700">
                        Critical
                      </span>
                    )}
                  </div>

                  <p className="mt-2 text-sm text-muted">
                    {step.instruction || "No instruction provided."}
                  </p>
                  <p className="mt-3 text-xs text-muted">
                    {step.minutes_before_procedure.toLocaleString()} minutes
                    before procedure
                  </p>

                  {reminder ? (
                    <div className="mt-4 border-t border-line pt-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-sm font-medium text-ink">
                          Reminder #{reminder.id}
                        </span>
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${statusClass}`}
                        >
                          {status.replace("_", " ")}
                        </span>
                      </div>

                      {reminder.status === "failed" && (
                        <div
                          role="alert"
                          className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3"
                        >
                          <div className="flex items-start gap-2">
                            <AlertTriangle
                              size={18}
                              className="mt-0.5 shrink-0 text-red-700"
                            />
                            <div>
                              <p className="text-sm font-bold text-red-800">
                                {reminder.status === "failed"
                                  ? "Failed delivery — action required"
                                  : "Missed reminder — action required"}
                              </p>
                              <p className="mt-1 text-sm text-red-700">
                                {reminder.status === "failed"
                                  ? "Delivery attempts were exhausted. Clinic staff should contact the patient and verify their preparation instructions."
                                  : "The reminder was sent but has not been confirmed. Clinic staff should contact the patient and verify their preparation instructions."}
                              </p>
                              <p className="mt-2 text-sm font-semibold text-red-800">
                                Attempts: {reminder.delivery_attempts ?? 0}/3
                              </p>
                            </div>
                          </div>
                        </div>
                      )}

                      <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                        <div>
                          <dt className="text-xs text-muted">Scheduled</dt>
                          <dd className="mt-1 text-ink">
                            {formatDate(reminder.scheduled_at)}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-xs text-muted">Sent</dt>
                          <dd className="mt-1 text-ink">
                            {formatDate(reminder.sent_at)}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-xs text-muted">Confirmed</dt>
                          <dd className="mt-1 text-ink">
                            {formatDate(reminder.confirmed_at)}
                          </dd>
                        </div>
                      </dl>
                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-muted">
                      No reminder record exists for this step.
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}


function SettingsPage() {
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState("10");
  const [retryAttempts, setRetryAttempts] = useState("3");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadSettings() {
      try {
        setLoading(true);
        setError("");

        const response = await fetch("/api/settings/");

        if (!response.ok) {
          const message = await response.text();
          throw new Error(`Could not load settings (${response.status}).`);
        }

        const data = await response.json();

        setNotificationsEnabled(data.notifications_enabled);
        setRefreshInterval(String(data.refresh_interval));
        setRetryAttempts(String(data.retry_attempts));
      } catch (err) {
        setError(err.message || "Could not load settings.");
      } finally {
        setLoading(false);
      }
    }

    loadSettings();
  }, []);

  async function saveSettings(event) {
    event.preventDefault();

    try {
      setSaving(true);
      setSaved(false);
      setError("");

      const response = await fetch("/api/settings/", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          notifications_enabled: notificationsEnabled,
          refresh_interval: Number(refreshInterval),
          retry_attempts: Number(retryAttempts),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || `Save failed (${response.status}).`);
      }

      setNotificationsEnabled(data.notifications_enabled);
      setRefreshInterval(String(data.refresh_interval));
      setRetryAttempts(String(data.retry_attempts));
      setSaved(true);
    } catch (err) {
      setError(err.message || "Could not save settings.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-muted">Loading settings...</p>;
  }

  return (
    <div className="space-y-7">
      <div>
        <p className="mb-2 text-xs font-medium text-slate-400">
          Workspace / Settings
        </p>
        <h1 className="text-[28px] font-semibold tracking-tight text-ink">
          Settings
        </h1>
        <p className="mt-1 text-sm text-muted">
          Manage your PrepBuddy dashboard preferences.
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-700">{error}</p>
      )}

      <form onSubmit={saveSettings} className="space-y-5">
        <section className="card p-5 sm:p-6">
          <h2 className="text-base font-semibold text-ink">Notifications</h2>
          <p className="mt-1 text-sm text-muted">
            Control the notification preference for this dashboard.
          </p>

          <label className="mt-5 flex items-center justify-between gap-4">
            <span>
              <span className="block text-sm font-medium text-ink">
                Enable dashboard notifications
              </span>
              <span className="mt-1 block text-xs text-muted">
                This preference does not independently change WhatsApp delivery.
              </span>
            </span>
            <input
              type="checkbox"
              checked={notificationsEnabled}
              disabled={saving}
              onChange={(event) => {
                setNotificationsEnabled(event.target.checked);
                setSaved(false);
              }}
              className="h-4 w-4 accent-indigo-600"
            />
          </label>
        </section>

        <section className="card p-5 sm:p-6">
          <h2 className="text-base font-semibold text-ink">Dashboard</h2>
          <p className="mt-1 text-sm text-muted">
            Choose your preferred dashboard refresh interval.
          </p>

          <label className="mt-5 block text-sm font-medium text-ink">
            Refresh interval
            <select
              value={refreshInterval}
              disabled={saving}
              onChange={(event) => {
                setRefreshInterval(event.target.value);
                setSaved(false);
              }}
              className="mt-2 block w-full max-w-sm rounded-lg border border-line bg-white px-3 py-2 text-sm"
            >
              <option value="10">Every 10 seconds</option>
              <option value="30">Every 30 seconds</option>
              <option value="60">Every 60 seconds</option>
            </select>
          </label>
        </section>

        <section className="card p-5 sm:p-6">
          <h2 className="text-base font-semibold text-ink">
            Reminder delivery
          </h2>
          <p className="mt-1 text-sm text-muted">
            Saved retry preference. This does not change backend retry logic yet.
          </p>

          <label className="mt-5 block text-sm font-medium text-ink">
            Maximum delivery attempts
            <select
              value={retryAttempts}
              disabled={saving}
              onChange={(event) => {
                setRetryAttempts(event.target.value);
                setSaved(false);
              }}
              className="mt-2 block w-full max-w-sm rounded-lg border border-line bg-white px-3 py-2 text-sm"
            >
              <option value="1">1 attempt</option>
              <option value="2">2 attempts</option>
              <option value="3">3 attempts</option>
            </select>
          </label>
        </section>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {saving ? "Saving..." : "Save preferences"}
          </button>

          {saved && (
            <p role="status" className="text-sm text-emerald-700">
              Preferences saved to the database.
            </p>
          )}
        </div>
      </form>
    </div>
  );
}


function getCookie(name) {
  const cookie = document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${name}=`));

  return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
}


function DoctorProfilePage({ doctor, setDoctor }) {
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const [draft, setDraft] = useState(doctor);

  // Load the profile from Django when the page opens.
  useEffect(() => {
    async function loadProfile() {
      try {
        setLoading(true);
        setError("");

        const response = await fetch("/api/doctor-profile/");

        if (!response.ok) {
          throw new Error(`Unable to load profile (${response.status}).`);
        }

        const data = await response.json();

        const profile = {
          name: data.full_name ?? "",
          role: data.professional_role ?? "",
          specialty: data.specialty ?? "",
          email: data.email ?? "",
          phone: data.phone ?? "",
        };

        setDoctor(profile);
        setDraft(profile);
      } catch (err) {
        setError(
          err.message || "Could not load the profile. Check your connection."
        );
      } finally {
        setLoading(false);
      }
    }

    loadProfile();
  }, []);

  function startEditing() {
    setDraft({ ...doctor });
    setSaved(false);
    setError("");
    setEditing(true);
  }

  async function saveProfile(event) {
    event.preventDefault();

    try {
      setSaving(true);
      setError("");
      setSaved(false);

      const response = await fetch("/api/doctor-profile/", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          full_name: draft.name,
          professional_role: draft.role,
          specialty: draft.specialty,
          email: draft.email,
          phone: draft.phone,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Failed to save profile.");
      }

      const profile = {
        name: data.full_name ?? draft.name,
        role: data.professional_role ?? draft.role,
        specialty: data.specialty ?? draft.specialty,
        email: data.email ?? draft.email,
        phone: data.phone ?? draft.phone,
      };

      setDoctor(profile);
      setDraft(profile);
      setEditing(false);
      setSaved(true);
    } catch (err) {
      setError(err.message || "Could not save the profile.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-muted">Loading doctor profile...</p>;
  }

  return (
    <div className="space-y-7">
      <div>
        <p className="mb-2 text-xs font-medium text-slate-400">
          Workspace / Doctor profile
        </p>
        <h1 className="text-[28px] font-semibold tracking-tight text-ink">
          Doctor profile
        </h1>
        <p className="mt-1 text-sm text-muted">
          View and manage your professional information.
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}

      {saved && (
        <p role="status" className="text-sm text-emerald-700">
          Profile saved successfully to the database.
        </p>
      )}

      <section className="card p-5 sm:p-7">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="grid h-20 w-20 shrink-0 place-items-center rounded-full bg-[#f1e6ff] text-2xl font-bold text-[#7b43b2]">
            {doctor.name
              .split(/\s+/)
              .filter(Boolean)
              .map((part) => part[0])
              .join("")
              .slice(0, 2)
              .toUpperCase()}
          </div>

          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-semibold text-ink">
              {doctor.name}
            </h2>
            <p className="mt-1 text-sm text-muted">{doctor.role}</p>
            <p className="mt-1 text-sm text-muted">{doctor.specialty}</p>
          </div>

          {!editing && (
            <button
              type="button"
              onClick={startEditing}
              className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white"
            >
              Edit profile
            </button>
          )}
        </div>

        {editing ? (
          <form
            onSubmit={saveProfile}
            className="mt-7 space-y-4 border-t border-line pt-6"
          >
            {[
              ["name", "Full name"],
              ["role", "Professional role"],
              ["specialty", "Specialty"],
              ["email", "Email address"],
              ["phone", "Phone number"],
            ].map(([field, label]) => (
              <label key={field} className="block">
                <span className="text-sm font-medium text-ink">
                  {label}
                </span>
                <input
                  type={field === "email" ? "email" : "text"}
                  value={draft[field]}
                  onChange={(event) => {
                    setDraft((current) => ({
                      ...current,
                      [field]: event.target.value,
                    }));
                    setSaved(false);
                  }}
                  required={["name", "role", "specialty"].includes(field)}
                  disabled={saving}
                  className="mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand disabled:opacity-60 sm:max-w-xl"
                />
              </label>
            ))}

            <div className="flex flex-wrap gap-3 pt-2">
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {saving ? "Saving..." : "Save profile"}
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => {
                  setDraft({ ...doctor });
                  setEditing(false);
                  setError("");
                }}
                className="rounded-lg border border-line px-4 py-2 text-sm font-semibold text-ink disabled:opacity-60"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <dl className="mt-7 grid gap-5 border-t border-line pt-6 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-muted">Email address</dt>
              <dd className="mt-1 text-sm font-medium text-ink">
                {doctor.email || "Not provided"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Phone number</dt>
              <dd className="mt-1 text-sm font-medium text-ink">
                {doctor.phone || "Not provided"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Account role</dt>
              <dd className="mt-1 text-sm font-medium text-ink">
                {doctor.role}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Specialty</dt>
              <dd className="mt-1 text-sm font-medium text-ink">
                {doctor.specialty}
              </dd>
            </div>
          </dl>
        )}
      </section>

      <p className="text-xs text-muted">
        Profile information is loaded from and saved to the Django database.
      </p>
    </div>
  );
}

export function Protocols() {
  const [protocols, setProtocols] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function fetchProtocols() {
      try {
        const response = await fetch(
          "http://127.0.0.1:8000/api/protocols/"
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (!cancelled) {
          setProtocols(data.protocols ?? []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load protocols.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchProtocols();

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <div className="p-8 text-sm text-muted">Loading protocols...</div>;
  }

  if (error) {
    return (
      <div className="card p-8">
        <h1 className="text-xl font-semibold text-ink">Could not load protocols</h1>
        <p className="mt-2 text-sm text-rose-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-7">
      <div>
        <p className="mb-2 text-xs font-medium text-slate-400">
          Overview / Protocols
        </p>
        <h1 className="text-[28px] font-semibold tracking-tight text-ink">
          Preparation Protocols
        </h1>
        <p className="mt-1 text-sm text-muted">
          Clinical preparation instructions managed by PrepBuddy.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {protocols.map((protocol) => (
          <article
            key={protocol.id}
            className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  {protocol.name}
                </h2>
                <p className="mt-2 text-sm text-slate-500">
                  {protocol.description || "No description provided."}
                </p>
              </div>

              <span
                className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${
                  protocol.is_active
                    ? "bg-emerald-50 text-emerald-700"
                    : "bg-slate-100 text-slate-600"
                }`}
              >
                {protocol.is_active ? "Active" : "Inactive"}
              </span>
            </div>

            <div className="mt-5 border-t border-slate-100 pt-4">
              <p className="text-sm font-medium text-slate-700">
                Preparation steps ({protocol.step_count})
              </p>

              <div className="mt-4 space-y-3">
                {protocol.steps.map((step, index) => (
                  <div key={step.id} className="rounded-xl bg-slate-50 p-4">
                    <div className="flex items-start gap-3">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
                        {index + 1}
                      </span>

                      <div className="min-w-0 flex-1">
                        <h3 className="font-medium text-slate-800">
                          {step.title}
                        </h3>
                        <p className="mt-1 text-sm text-slate-500">
                          {step.instruction || "No instructions provided."}
                        </p>
                        <p className="mt-2 text-xs text-slate-500">
                          {step.minutes_before_procedure.toLocaleString()}{" "}
                          minutes before procedure
                        </p>

                        <div className="mt-2 flex flex-wrap gap-2">
                          {step.is_critical && (
                            <span className="rounded-full bg-rose-50 px-2 py-1 text-xs text-rose-700">
                              Critical
                            </span>
                          )}

                          {step.requires_confirmation && (
                            <span className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">
                              Confirmation required
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </article>
        ))}
      </div>

      {protocols.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
          No protocols found.
        </div>
      )}
    </div>
  );
}


export default function App() {
  const [active, setActive] = useState("Dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [selectedProcedureId, setSelectedProcedureId] = useState(1);

  const [doctor, setDoctor] = useState({
    name: "",
    role: "",
    specialty: "",
    email: "",
    phone: "",
  });

  useEffect(() => {
    async function loadDoctorProfile() {
      try {
        const response = await fetch("/api/doctor-profile/");

        if (!response.ok) {
          throw new Error("Failed to load doctor profile");
        }

        const data = await response.json();

        setDoctor({
          name: data.full_name ?? "",
          role: data.professional_role ?? "",
          specialty: data.specialty ?? "",
          email: data.email ?? "",
          phone: data.phone ?? "",
        });
      } catch (error) {
        console.error("Unable to load doctor profile:", error);
      }
    }

    loadDoctorProfile();
  }, []);

  const showToast = (message) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2800);
  };

  return (
    <div className="flex min-h-screen bg-[#f8fafc]">
      <Sidebar
        active={active}
        doctor={doctor}
        onNavigate={(page) => {
          setActive(page);
          if (page !== "Dashboard") {
            showToast(`${page} view is ready to connect to your workspace`);
          }
        }}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-[72px] items-center justify-between border-b border-line bg-white/90 px-5 backdrop-blur sm:px-8">
          <div className="flex items-center gap-3">
            <button
              aria-label="Open navigation"
              className="rounded-lg p-2 text-slate-500 hover:bg-slate-50 lg:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu size={21} />
            </button>
            <div className="hidden text-sm font-medium text-slate-400 sm:block">
              Thursday, 08 October 2026
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              aria-label="Notifications"
              onClick={() => showToast("You are all caught up")}
              className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-50"
            >
              <Bell size={19} />
              <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-rose-500 ring-2 ring-white" />
            </button>

            <div className="hidden h-6 w-px bg-line sm:block" />

            <div className="grid h-8 w-8 place-items-center rounded-full bg-[#f1e6ff] text-[10px] font-bold text-[#7b43b2]">
              {(doctor.name || "Doctor")
                .split(/\s+/)
                .filter(Boolean)
                .map((part) => part[0])
                .join("")
                .slice(0, 2)
                .toUpperCase()}
            </div>
          </div>
        </header>

        <div className="mx-auto max-w-[1440px] p-5 sm:p-8">
          {active === "Dashboard" ? (
            <Dashboard
              onOpenProcedure={(procedureId) => {
                setSelectedProcedureId(procedureId);
                setActive("Procedure timeline");
              }}
              onToast={showToast}
            />
          ) : active === "Patient details" ? (
            <PatientDetails />
          ) : active === "Procedure timeline" ? (
            <ProcedureTimeline
              procedureId={selectedProcedureId}
              onBack={() => setActive("Dashboard")}
            />
          ) : active === "Protocols" ? (
            <Protocols />
          ) : active === "Settings" ? (
            <SettingsPage />
          ) : active === "Doctor profile" ? (
            <DoctorProfilePage doctor={doctor} setDoctor={setDoctor} />
          ) : (
            <div className="card grid min-h-[420px] place-items-center p-8 text-center">
              <div>
                <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-brand-soft text-brand">
                  <ClipboardList size={24} />
                </div>
                <h1 className="text-xl font-semibold text-ink">{active}</h1>
                <p className="mt-2 max-w-sm text-sm text-muted">
                  This page will be connected next.
                </p>
              </div>
            </div>
          )}
        </div>
      </main>

      {toast && (
        <div
          role="status"
          className="fixed bottom-5 right-5 z-50 flex items-center gap-3 rounded-xl bg-ink px-4 py-3 text-sm font-medium text-white shadow-xl"
        >
          <Check size={17} className="text-emerald-400" />
          {toast}
        </div>
      )}
    </div>
  );
}
