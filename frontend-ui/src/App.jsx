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
  MessageCircle,
  MoreHorizontal,
  Search,
  LogOut,
  Settings,
  ShieldCheck,
  Stethoscope,
  Users,
  X,
} from "lucide-react";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Patient details", icon: Users },
  { label: "Protocols", icon: ClipboardList },
  { label: "Create Procedure", icon: CalendarDays },
];

const IST_OFFSET_MINUTES = 330;

function istDateTimeToUtc(dateTimeValue) {
  // datetime-local gives "YYYY-MM-DDTHH:mm" without a timezone.
  // Interpret that wall-clock time as IST (UTC+05:30).
  const match = dateTimeValue.match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/
  );

  if (!match) return null;

  const [, year, month, day, hour, minute] = match.map(Number);
  const utcMilliseconds = Date.UTC(
    year,
    month - 1,
    day,
    hour,
    minute
  ) - IST_OFFSET_MINUTES * 60 * 1000;

  const date = new Date(utcMilliseconds);

  // Reject invalid calendar dates instead of silently normalizing them.
  const check = new Date(
    Date.UTC(year, month - 1, day, hour, minute)
  );

  if (
    check.getUTCFullYear() !== year ||
    check.getUTCMonth() !== month - 1 ||
    check.getUTCDate() !== day ||
    check.getUTCHours() !== hour ||
    check.getUTCMinutes() !== minute
  ) {
    return null;
  }

  return date;
}

function getIstDateTimeLocalValue(date = new Date()) {
  // Display a UTC instant as an IST wall-clock value for datetime-local.
  const istMilliseconds = date.getTime() + IST_OFFSET_MINUTES * 60 * 1000;
  return new Date(istMilliseconds).toISOString().slice(0, 16);
}

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
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[254px] flex-col border-r border-line bg-[#fbfcff] px-4 py-5 transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
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
          <form method="post" action="/logout/" className="px-1 pt-1">
            <input
              type="hidden"
              name="csrfmiddlewaretoken"
              value={getCookie("csrftoken")}
            />
            <button
              type="submit"
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-rose-600 transition hover:bg-rose-50"
            >
              <LogOut size={18} />
              Log Out
            </button>
          </form>
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
        "/api/procedures/",
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

          <div className="relative w-full sm:max-w-xs">
            <Search
              size={18}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search procedures..."
              aria-label="Search procedures"
              className="h-10 w-full rounded-lg border border-line bg-white pl-10 pr-3 text-sm text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10"
            />
          </div>

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
  const [patientSearch, setPatientSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [deletingPatientId, setDeletingPatientId] = useState(null);
  const [deleteError, setDeleteError] = useState("");
  const [deletingProcedureId, setDeletingProcedureId] = useState(null);
  const [procedureDeleteError, setProcedureDeleteError] = useState("");

  const filteredPatients = patients.filter((patient) => {
    const query = patientSearch.trim().toLowerCase();
    const searchableText = [
      patient.first_name,
      patient.last_name,
      `${patient.first_name ?? ""} ${patient.last_name ?? ""}`,
      patient.email,
      patient.phone_number,
      patient.id,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return searchableText.includes(query);
  });

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    phone_number: "",
    email: "",
  });

  const loadPatients = useCallback(async () => {
    const response = await fetch("/api/patients/", {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Could not load patients (${response.status}).`);
    }

    const data = await response.json();
    setPatients(data.patients ?? []);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetch("/api/patients/", {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`Could not load patients (${response.status}).`);
        }

        const data = await response.json();

        if (!cancelled) {
          setPatients(data.patients ?? []);
          setError("");
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

    load();

    return () => {
      cancelled = true;
    };
  }, []);

  function updateField(event) {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: value,
    }));

    setFieldErrors((current) => ({
      ...current,
      [name]: "",
    }));

    setFormError("");
    setSuccess("");
  }

  async function createPatient(event) {
    event.preventDefault();

    setSubmitting(true);
    setFormError("");
    setFieldErrors({});
    setSuccess("");
    setError("");

    try {
      const response = await fetch("/api/patients/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
          phone_number: form.phone_number.trim(),
          email: form.email.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (data.errors) {
          setFieldErrors(data.errors);
          setFormError("Please correct the highlighted fields.");
        } else {
          setFormError(
            data.error || `Could not create patient (${response.status}).`
          );
        }
        return;
      }

      setForm({
        first_name: "",
        last_name: "",
        phone_number: "",
        email: "",
      });

      await loadPatients();
      setShowForm(false);
      setSuccess(
        `Patient ${data.patient.first_name} ${data.patient.last_name} added successfully.`
      );
    } catch (err) {
      setFormError(
        err.message || "Unable to create patient. Check your connection."
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function deletePatient(patient) {
    const confirmed = window.confirm(
      `Delete patient "${patient.first_name} ${patient.last_name}"? This cannot be undone.`
    );

    if (!confirmed) return;

    setDeletingPatientId(patient.id);
    setDeleteError("");
    setSuccess("");
    setError("");

    try {
      const response = await fetch(`/api/patients/${patient.id}/`, {
        method: "DELETE",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error || `Could not delete patient (${response.status}).`
        );
      }

      await loadPatients();
      setSuccess(
        `Patient ${patient.first_name} ${patient.last_name} deleted successfully.`
      );
    } catch (err) {
      setDeleteError(err.message || "Unable to delete patient.");
    } finally {
      setDeletingPatientId(null);
    }
  }

  async function deleteProcedureFromPatient(procedure) {
    const confirmed = window.confirm(
      `Delete procedure "${procedure.procedure_name}"? Its reminders will also be deleted. This action cannot be undone.`
    );

    if (!confirmed) return;

    setDeletingProcedureId(procedure.id);
    setProcedureDeleteError("");
    setDeleteError("");
    setSuccess("");

    try {
      const response = await fetch(`/api/procedures/${procedure.id}/`, {
        method: "DELETE",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error || `Could not delete procedure (${response.status}).`
        );
      }

      await loadPatients();
      setSuccess(
        `Procedure "${procedure.procedure_name}" deleted successfully.`
      );
    } catch (err) {
      setProcedureDeleteError(
        err.message || "Unable to delete this procedure."
      );
    } finally {
      setDeletingProcedureId(null);
    }
  }

  if (loading) {
    return <div className="p-8 text-sm text-muted">Loading patients...</div>;
  }

  if (error) {
    return (
      <div className="card p-8">
        <h1 className="text-xl font-semibold text-ink">
          Could not load patients
        </h1>
        <p className="mt-2 text-sm text-rose-600">{error}</p>
        <button
          type="button"
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
      {procedureDeleteError && (
        <p
          role="alert"
          className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700"
        >
          {procedureDeleteError}
        </p>
      )}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="mb-2 text-xs font-medium text-slate-400">
            Overview / Patients
          </p>
          <h1 className="text-[28px] font-semibold tracking-tight text-ink">
            Patient details
          </h1>
          <p className="mt-1 text-sm text-muted">
            Manage patient records stored in the PrepBuddy database.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setShowForm((current) => !current);
            setFormError("");
            setFieldErrors({});
            setSuccess("");
          }}
          className="rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white"
        >
          {showForm ? "Cancel" : "+ Add Patient"}
        </button>
      </div>

      {success && (
        <p
          role="status"
          className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700"
        >
          {success}
        </p>
      )}

      {showForm && (
        <section className="card p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-ink">Add a patient</h2>
          <p className="mt-1 text-sm text-muted">
            Enter the patient's contact details. Fields marked * are required.
          </p>

          {formError && (
            <p
              role="alert"
              className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700"
            >
              {formError}
            </p>
          )}

          <form onSubmit={createPatient} className="mt-5 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="text-sm font-medium text-ink">
                  First name *
                </span>
                <input
                  name="first_name"
                  value={form.first_name}
                  onChange={updateField}
                  required
                  maxLength={100}
                  disabled={submitting}
                  autoComplete="given-name"
                  className="mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand disabled:opacity-60"
                />
                {fieldErrors.first_name && (
                  <span className="mt-1 block text-xs text-rose-600">
                    {fieldErrors.first_name}
                  </span>
                )}
              </label>

              <label className="block">
                <span className="text-sm font-medium text-ink">
                  Last name *
                </span>
                <input
                  name="last_name"
                  value={form.last_name}
                  onChange={updateField}
                  required
                  maxLength={100}
                  disabled={submitting}
                  autoComplete="family-name"
                  className="mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand disabled:opacity-60"
                />
                {fieldErrors.last_name && (
                  <span className="mt-1 block text-xs text-rose-600">
                    {fieldErrors.last_name}
                  </span>
                )}
              </label>

              <label className="block">
                <span className="text-sm font-medium text-ink">
                  Phone number *
                </span>
                <input
                  name="phone_number"
                  type="tel"
                  value={form.phone_number}
                  onChange={updateField}
                  required
                  maxLength={20}
                  disabled={submitting}
                  autoComplete="tel"
                  placeholder="+919876543210"
                  className="mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand disabled:opacity-60"
                />
                {fieldErrors.phone_number && (
                  <span className="mt-1 block text-xs text-rose-600">
                    {fieldErrors.phone_number}
                  </span>
                )}
              </label>

              <label className="block">
                <span className="text-sm font-medium text-ink">
                  Email address
                </span>
                <input
                  name="email"
                  type="email"
                  value={form.email}
                  onChange={updateField}
                  maxLength={254}
                  disabled={submitting}
                  autoComplete="email"
                  placeholder="patient@example.com"
                  className="mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand disabled:opacity-60"
                />
                {fieldErrors.email && (
                  <span className="mt-1 block text-xs text-rose-600">
                    {fieldErrors.email}
                  </span>
                )}
              </label>
            </div>

            <div className="flex flex-wrap gap-3 pt-2">
              <button
                type="submit"
                disabled={submitting}
                className="rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {submitting ? "Adding patient..." : "Save patient"}
              </button>

              <button
                type="button"
                disabled={submitting}
                onClick={() => {
                  setShowForm(false);
                  setFormError("");
                  setFieldErrors({});
                }}
                className="rounded-lg border border-line px-5 py-2.5 text-sm font-semibold text-ink disabled:opacity-60"
              >
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}
      {deleteError && (
          <div role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {deleteError}
          </div>
        )}

      <section className="card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-line px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="font-semibold text-ink">
            Registered patients ({filteredPatients.length})
          </h2>

          <div className="relative w-full sm:max-w-xs">
            <Search
              size={18}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="search"
              value={patientSearch}
              onChange={(event) => setPatientSearch(event.target.value)}
              placeholder="Search patients..."
              aria-label="Search patients"
              className="w-full rounded-lg border border-line bg-white py-2 pl-10 pr-3 text-sm text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10"
            />
          </div>
        </div>

        {filteredPatients.length === 0 ? (
          <p className="p-5 text-sm text-muted">
            {patientSearch.trim()
              ? "No patients match your search."
              : "No patients found."}
          </p>
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

                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
                      {(patient.procedures ?? []).length} procedure(s)
                    </span>

                    <button
                      type="button"
                      onClick={() => deletePatient(patient)}
                      disabled={deletingPatientId === patient.id}
                      className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {deletingPatientId === patient.id ? "Deleting..." : "Delete"}
                    </button>
                  </div>

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
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <StatusBadge status={procedure.status} />

                          <button
                            type="button"
                            onClick={() => deleteProcedureFromPatient(procedure)}
                            disabled={deletingProcedureId === procedure.id}
                            className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {deletingProcedureId === procedure.id ? "Deleting..." : "Delete procedure"}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function ProcedureTimeline({ procedureId, onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [confirmingId, setConfirmingId] = useState(null);
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [followUpDrafts, setFollowUpDrafts] = useState({});
  const [followUpSubmittingId, setFollowUpSubmittingId] = useState(null);
  const [followUpMessage, setFollowUpMessage] = useState("");
  const [followUpError, setFollowUpError] = useState("");
  const [deletingProcedure, setDeletingProcedure] = useState(false);
  const [deleteProcedureError, setDeleteProcedureError] = useState("");

  const loadTimeline = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setError("");

      const response = await fetch(
        `/api/procedures/${procedureId}/timeline/`,
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

  const confirmStep = async (reminder) => {
    if (!reminder?.confirmation_token) {
      setActionError("Confirmation token is unavailable.");
      setActionMessage("");
      return;
    }

    try {
      setConfirmingId(reminder.id);
      setActionMessage("");
      setActionError("");

      const response = await fetch(
        `/api/reminders/${encodeURIComponent(
           reminder.confirmation_token
         )}/confirm/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
          },
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.error || "Unable to confirm this preparation step."
        );
      }

      setActionMessage(result.message || "Preparation step confirmed.");
      await loadTimeline(true);
    } catch (err) {
      setActionError(err.message || "Unable to confirm this step.");
    } finally {
      setConfirmingId(null);
    }
  };

  const submitFollowUp = async (reminder) => {
    const draft = followUpDrafts[reminder.id] || {
      contact_outcome: "reached",
      preparation_status: "unknown",
      notes: "",
    };

    if (reminder.status !== "missed") {
      setFollowUpError("Follow-up can only be recorded for a missed reminder.");
      setFollowUpMessage("");
      return;
    }

    if (!getCookie("csrftoken")) {
      setFollowUpError(
        "CSRF token is missing. Reload the application through the Django login session and try again."
      );
      setFollowUpMessage("");
      return;
    }

    try {
      setFollowUpSubmittingId(reminder.id);
      setFollowUpError("");
      setFollowUpMessage("");

      const response = await fetch("/api/reminders/follow-ups/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          reminder_id: reminder.id,
          contact_outcome: draft.contact_outcome,
          preparation_status: draft.preparation_status,
          notes: draft.notes,
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.error ||
            (response.status === 403
              ? "Access denied. Check your login, staff role, and CSRF token."
              : "Unable to record staff follow-up.")
        );
      }

      setFollowUpMessage(
        `Follow-up recorded for reminder #${reminder.id}. Clinical review is still required.`
      );

      await loadTimeline(true);
    } catch (err) {
      setFollowUpError(err.message || "Unable to record staff follow-up.");
    } finally {
      setFollowUpSubmittingId(null);
    }
  };

  const updateFollowUpDraft = (reminderId, field, value) => {
    setFollowUpDrafts((previous) => ({
      ...previous,
      [reminderId]: {
        contact_outcome: "reached",
        preparation_status: "unknown",
        notes: "",
        ...previous[reminderId],
        [field]: value,
      },
    }));
  };

  async function deleteProcedure() {
    const confirmed = window.confirm(
      `Delete procedure "${data?.procedure?.procedure_name}"? Its reminders will also be deleted. This action cannot be undone.`
    );

    if (!confirmed) return;

    if (!getCookie("csrftoken")) {
      setDeleteProcedureError(
        "CSRF token is missing. Reload the application through the Django session and try again."
      );
      return;
    }

    setDeletingProcedure(true);
    setDeleteProcedureError("");
    setActionMessage("");
    setActionError("");

    try {
      const response = await fetch(`/api/procedures/${procedureId}/`, {
        method: "DELETE",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
        },
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.error || `Could not delete procedure (${response.status}).`
        );
      }

      onBack();
    } catch (err) {
      setDeleteProcedureError(
        err.message || "Unable to delete this procedure."
      );
    } finally {
      setDeletingProcedure(false);
    }
  }

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
      {actionMessage && (
        <p
          role="status"
          className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700"
        >
          {actionMessage}
        </p>
      )}

      {actionError && (
        <p
          role="alert"
          className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700"
        >
          {actionError}
        </p>
      )}

      <div>
        <p className="mb-2 text-xs font-medium text-slate-400">
          Overview / Procedure timeline
        </p>
        <h1 className="text-[28px] font-semibold tracking-tight text-ink">
          Procedure timeline
        </h1>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            onClick={onBack}
            className="rounded-lg border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-slate-50"
          >
            Back to workspace
          </button>

          <button
            onClick={() => loadTimeline(true)}
            disabled={refreshing || deletingProcedure}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {refreshing ? "Refreshing..." : "Refresh timeline"}
          </button>

          <button
            type="button"
            onClick={deleteProcedure}
            disabled={deletingProcedure || refreshing}
            className="rounded-lg border border-red-200 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {deletingProcedure ? "Deleting..." : "Delete procedure"}
          </button>
        </div>

        {deleteProcedureError && (
          <p
            role="alert"
            className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700"
          >
            {deleteProcedureError}
          </p>
        )}
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

                      {["pending", "sent", "failed"].includes(reminder.status) && (
                        <button
                          type="button"
                          onClick={() => confirmStep(reminder)}
                          disabled={confirmingId === reminder.id}
                          className="mt-3 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                        >
                          {confirmingId === reminder.id
                            ? "Confirming..."
                            : "Mark as completed"}
                        </button>
                      )}

                      {["failed", "missed"].includes(reminder.status) && (
                        <div
                          role="alert"
                          className={`mt-3 rounded-lg border p-4 ${
                            reminder.status === "missed"
                              ? "border-red-200 bg-red-50"
                              : "border-amber-200 bg-amber-50"
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            <AlertTriangle
                              size={20}
                              className={`mt-0.5 shrink-0 ${
                                reminder.status === "missed"
                                  ? "text-red-700"
                                  : "text-amber-700"
                              }`}
                            />

                            <div className="min-w-0 flex-1">
                              <p
                                className={`text-sm font-bold ${
                                  reminder.status === "missed"
                                    ? "text-red-800"
                                    : "text-amber-800"
                                }`}
                              >
                                {reminder.status === "missed"
                                  ? "Critical preparation step needs review"
                                  : "Reminder delivery failed"}
                              </p>

                              <p className="mt-1 text-sm text-slate-700">
                                {reminder.status === "missed"
                                  ? "This step was not confirmed in time. Clinic staff must contact the patient, verify what preparation was completed, and consult the approved clinical protocol before deciding what happens next."
                                  : "The reminder could not be delivered after the available attempts. Clinic staff should contact the patient and verify that the preparation instructions were received."}
                              </p>

                              {reminder.status === "missed" ? (
                                <div className="mt-3 rounded-lg border border-red-200 bg-white p-3">
                                  <p className="text-sm font-semibold text-slate-800">
                                    Recommended next steps
                                  </p>
                                  <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-700">
                                    <li>Contact the patient.</li>
                                    <li>Record whether the preparation step was completed.</li>
                                    <li>Refer the case to clinical staff for a decision.</li>
                                  </ol>
                                  <p className="mt-3 text-xs text-slate-500">
                                    This reminder remains marked as missed until handled through
                                    an authorized workflow.
                                  </p>
                                </div>
                              ) : (
                                <p className="mt-2 text-sm font-semibold text-amber-800">
                                  Delivery attempts: {reminder.delivery_attempts ?? 0}/3
                                </p>
                              )}
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
  const [protocolSearch, setProtocolSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [success, setSuccess] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingProtocolId, setDeletingProtocolId] = useState(null);
  const [deleteError, setDeleteError] = useState("");

  const filteredProtocols = protocols.filter((protocol) => {
    const query = protocolSearch.trim().toLowerCase();

    const searchableText = [
      protocol.name,
      protocol.description,
      protocol.id,
      ...(protocol.steps ?? []).flatMap((step) => [
        step.title,
        step.instruction,
      ]),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return searchableText.includes(query);
  });

  const emptyStep = () => ({
    title: "",
    instruction: "",
    minutes_before_procedure: "60",
    requires_confirmation: true,
    is_critical: false,
  });

  const [form, setForm] = useState({
    name: "",
    description: "",
    is_active: true,
    steps: [emptyStep()],
  });

  const loadProtocols = useCallback(async () => {
    const response = await fetch("/api/protocols/", {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Could not load protocols (${response.status}).`);
    }

    const data = await response.json();
    setProtocols(data.protocols ?? []);
  }, []);

  async function deleteProtocol(protocol) {
    const confirmed = window.confirm(
      `Delete protocol "${protocol.name}"? This cannot be undone.`
    );

    if (!confirmed) return;

    setDeletingProtocolId(protocol.id);
    setDeleteError("");
    setSuccess("");
    setFormError("");

    try {
      const response = await fetch(
        `/api/protocols/?id=${protocol.id}`,
        {
          method: "DELETE",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
          },
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error || `Could not delete protocol (${response.status}).`
        );
      }

      await loadProtocols();
      setSuccess(`Protocol "${protocol.name}" deleted successfully.`);
    } catch (err) {
      setDeleteError(err.message || "Unable to delete protocol.");
    } finally {
      setDeletingProtocolId(null);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function fetchProtocols() {
      try {
        const response = await fetch("/api/protocols/", {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (!cancelled) {
          setProtocols(data.protocols ?? []);
          setError("");
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

  function updateStep(index, field, value) {
    setForm((current) => ({
      ...current,
      steps: current.steps.map((step, i) =>
        i === index ? { ...step, [field]: value } : step
      ),
    }));
    setFormError("");
    setSuccess("");
  }

  function updateProtocolField(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
    setFormError("");
    setSuccess("");
  }

  function resetForm() {
    setForm({
      name: "",
      description: "",
      is_active: true,
      steps: [emptyStep()],
    });
    setFormError("");
  }

  async function createProtocol(event) {
    event.preventDefault();
    setSaving(true);
    setFormError("");
    setSuccess("");

    const payload = {
      name: form.name.trim(),
      description: form.description.trim(),
      is_active: form.is_active,
      steps: form.steps.map((step, index) => ({
        title: step.title.trim(),
        instruction: step.instruction.trim(),
        minutes_before_procedure: Number(
          step.minutes_before_procedure
        ),
        requires_confirmation: step.requires_confirmation,
        is_critical: step.is_critical,
        order: index,
      })),
    };

    try {
      const response = await fetch("/api/protocols/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        const details = data.errors
          ? Object.entries(data.errors)
              .map(([field, message]) => `${field}: ${message}`)
              .join(" ")
          : data.error || `Request failed (${response.status}).`;

        throw new Error(details);
      }

      await loadProtocols();
      setSuccess(`Protocol "${data.protocol.name}" created successfully.`);
      resetForm();
      setShowForm(false);
    } catch (err) {
      setFormError(
        err.message || "Unable to save the protocol."
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="p-8 text-sm text-muted">Loading protocols...</div>;
  }

  if (error) {
    return (
      <div className="card p-8">
        <h1 className="text-xl font-semibold text-ink">
          Could not load protocols
        </h1>
        <p className="mt-2 text-sm text-rose-600">{error}</p>
        <button
          type="button"
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
      {deleteError && (
        <p
          role="alert"
          className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700"
        >
          {deleteError}
        </p>
      )}

      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="mb-2 text-xs font-medium text-slate-400">
            Overview / Protocols
          </p>
          <h1 className="text-[28px] font-semibold tracking-tight text-ink">
            Preparation Protocols
          </h1>
          <p className="mt-1 text-sm text-muted">
            Manage protocols and their preparation steps.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setShowForm((current) => !current);
            setFormError("");
            setSuccess("");
          }}
          className="rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white"
        >
          {showForm ? "Cancel" : "+ Add Protocol"}
        </button>
      </div>

      {success && (
        <p
          role="status"
          className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700"
        >
          {success}
        </p>
      )}

      {showForm && (
        <section className="card p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-ink">
            Create preparation protocol
          </h2>
          <p className="mt-1 text-sm text-muted">
            Add a protocol and at least one preparation step.
          </p>

          {formError && (
            <p
              role="alert"
              className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700"
            >
              {formError}
            </p>
          )}

          <form onSubmit={createProtocol} className="mt-5 space-y-5">
            <label className="block">
              <span className="text-sm font-medium text-ink">
                Protocol name *
              </span>
              <input
                name="name"
                value={form.name}
                onChange={updateProtocolField}
                required
                maxLength={200}
                disabled={saving}
                className="mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand"
                placeholder="Example: Demo Preparation Protocol"
              />
            </label>

            <label className="block">
              <span className="text-sm font-medium text-ink">
                Description
              </span>
              <textarea
                name="description"
                value={form.description}
                onChange={updateProtocolField}
                rows={3}
                disabled={saving}
                className="mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand"
                placeholder="Describe the purpose of this demo protocol"
              />
            </label>

            <label className="flex items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                checked={form.is_active}
                disabled={saving}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    is_active: event.target.checked,
                  }))
                }
                className="h-4 w-4 accent-indigo-600"
              />
              Active protocol
            </label>

            <div className="border-t border-line pt-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="font-semibold text-ink">
                  Preparation steps ({form.steps.length})
                </h3>
                <button
                  type="button"
                  disabled={saving}
                  onClick={() =>
                    setForm((current) => ({
                      ...current,
                      steps: [...current.steps, emptyStep()],
                    }))
                  }
                  className="rounded-lg border border-line px-3 py-2 text-sm font-semibold text-ink disabled:opacity-50"
                >
                  + Add step
                </button>
              </div>

              <div className="mt-4 space-y-5">
                {form.steps.map((step, index) => (
                  <div
                    key={index}
                    className="rounded-xl border border-line bg-slate-50 p-4"
                  >
                    <div className="mb-4 flex items-center justify-between gap-3">
                      <h4 className="font-semibold text-ink">
                        Step {index + 1}
                      </h4>
                      {form.steps.length > 1 && (
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() =>
                            setForm((current) => ({
                              ...current,
                              steps: current.steps.filter(
                                (_, i) => i !== index
                              ),
                            }))
                          }
                          className="text-sm font-medium text-rose-600 disabled:opacity-50"
                        >
                          Remove step
                        </button>
                      )}
                    </div>

                    <div className="space-y-4">
                      <label className="block">
                        <span className="text-sm font-medium text-ink">
                          Step title *
                        </span>
                        <input
                          value={step.title}
                          onChange={(event) =>
                            updateStep(index, "title", event.target.value)
                          }
                          required
                          maxLength={200}
                          disabled={saving}
                          className="mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 text-sm"
                          placeholder="Demo step title"
                        />
                      </label>

                      <label className="block">
                        <span className="text-sm font-medium text-ink">
                          Instruction *
                        </span>
                        <textarea
                          value={step.instruction}
                          onChange={(event) =>
                            updateStep(
                              index,
                              "instruction",
                              event.target.value
                            )
                          }
                          required
                          rows={3}
                          disabled={saving}
                          className="mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 text-sm"
                          placeholder="Enter demo instruction text"
                        />
                      </label>

                      <label className="block sm:max-w-xs">
                        <span className="text-sm font-medium text-ink">
                          Minutes before procedure *
                        </span>
                        <input
                          type="number"
                          min="0"
                          step="1"
                          required
                          value={step.minutes_before_procedure}
                          onChange={(event) =>
                            updateStep(
                              index,
                              "minutes_before_procedure",
                              event.target.value
                            )
                          }
                          disabled={saving}
                          className="mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 text-sm"
                        />
                      </label>

                      <div className="flex flex-wrap gap-x-6 gap-y-3">
                        <label className="flex items-center gap-2 text-sm text-ink">
                          <input
                            type="checkbox"
                            checked={step.requires_confirmation}
                            disabled={saving}
                            onChange={(event) =>
                              updateStep(
                                index,
                                "requires_confirmation",
                                event.target.checked
                              )
                            }
                            className="h-4 w-4 accent-indigo-600"
                          />
                          Requires confirmation
                        </label>

                        <label className="flex items-center gap-2 text-sm text-ink">
                          <input
                            type="checkbox"
                            checked={step.is_critical}
                            disabled={saving}
                            onChange={(event) =>
                              updateStep(
                                index,
                                "is_critical",
                                event.target.checked
                              )
                            }
                            className="h-4 w-4 accent-rose-600"
                          />
                          Critical step
                        </label>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
            >
              {saving ? "Saving protocol..." : "Save protocol"}
            </button>
          </form>
        </section>
      )}

      <div className="relative w-full sm:max-w-md">
        <Search
          size={18}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
        />
        <input
          type="search"
          value={protocolSearch}
          onChange={(event) => setProtocolSearch(event.target.value)}
          placeholder="Search protocols..."
          aria-label="Search protocols"
          className="w-full rounded-lg border border-line bg-white py-2.5 pl-10 pr-3 text-sm text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10"
        />
      </div>

      {filteredProtocols.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          {protocolSearch.trim()
            ? "No protocols match your search."
            : "No protocols found."}
        </div>
      ) : (
        <div className="grid gap-5 lg:grid-cols-2">
          {filteredProtocols.map((protocol) => (
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

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => deleteProtocol(protocol)}
                disabled={deletingProtocolId === protocol.id}
                className="rounded-lg border border-red-200 px-3 py-1.5 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deletingProtocolId === protocol.id
                  ? "Deleting..."
                  : "Delete protocol"}
              </button>
            </div>

            <div className="mt-5 border-t border-slate-100 pt-4">
              <p className="text-sm font-medium text-slate-700">
                Preparation steps ({protocol.step_count})
              </p>

              <div className="mt-4 space-y-3">
                {(protocol.steps ?? []).map((step, index) => (
                  <div
                    key={step.id}
                    className="rounded-xl bg-slate-50 p-4"
                  >
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
                          {Number(
                            step.minutes_before_procedure
                          ).toLocaleString()}{" "}
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
      )}
    </div>
  );
}

function PreparationAssistant() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Hello! I can help you find information in the stored preparation protocols. I will let you know when an answer is not available.",
      sources: [],
      needsClinicalTeam: false,
    },
  ]);
  const [question, setQuestion] = useState("");
  const [procedures, setProcedures] = useState([]);
  const [procedureId, setProcedureId] = useState("");
  const [loadingProcedures, setLoadingProcedures] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    async function loadProcedures() {
      try {
        const response = await fetch("/api/procedures/");
        if (!response.ok) {
          throw new Error("Unable to load procedures.");
        }

        const data = await response.json();

        if (!cancelled) {
          const available = data.procedures || [];
          setProcedures(available);
          setProcedureId(available.length ? String(available[0].id) : "");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load procedures.");
        }
      } finally {
        if (!cancelled) setLoadingProcedures(false);
      }
    }

    loadProcedures();

    return () => {
      cancelled = true;
    };
  }, []);

  async function sendQuestion(event) {
    event.preventDefault();

    const text = question.trim();
    if (!text || loading) return;

    if (!procedureId) {
      setError("Select a procedure before asking a question.");
      return;
    }

    setMessages((current) => [
      ...current,
      { role: "user", text },
    ]);
    setQuestion("");
    setError("");
    setLoading(true);

    try {
      const response = await fetch("/api/chatbot/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": Me("csrftoken")
        },
        body: JSON.stringify({
          question: text,
          procedure_id: Number(procedureId),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || `Request failed (${response.status})`);
      }

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: data.answer || "No answer was returned.",
          sources: data.sources || [],
          needsClinicalTeam: Boolean(data.needs_clinical_team),
        },
      ]);
    } catch (err) {
      setError(
        err.message || "Unable to contact the assistant. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mx-auto max-w-4xl">
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-soft text-brand">
            <MessageCircle size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-ink">
              Preparation Assistant
            </h1>
            <p className="mt-1 text-sm text-muted">
              Find answers in stored procedure-preparation instructions.
            </p>
          </div>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="flex items-center gap-3 border-b border-line p-4">
          <div className="grid h-10 w-10 place-items-center rounded-full bg-emerald-50 text-emerald-700">
            <ShieldCheck size={20} />
          </div>
          <div>
            <p className="text-sm font-semibold text-ink">
              PrepBuddy Assistant
            </p>
            <p className="text-xs text-muted">
              Answers are limited to stored protocol information.
            </p>
          </div>
          <span className="ml-auto rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
            Online
          </span>
        </div>

        <div
          aria-live="polite"
          aria-label="Conversation"
          className="max-h-[480px] min-h-[300px] space-y-4 overflow-y-auto bg-slate-50/70 p-4 sm:p-6"
        >
          {messages.map((message, index) => (
            <div
              key={`${index}-${message.role}`}
              className={`flex ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-6 sm:max-w-[80%] ${
                  message.role === "user"
                    ? "rounded-br-md bg-brand text-white"
                    : "rounded-bl-md border border-line bg-white text-ink"
                }`}
              >
                <p className="whitespace-pre-wrap">{message.text}</p>

                {message.sources?.length > 0 && (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <p className="mb-2 text-xs font-semibold">
                      Matched protocol steps
                    </p>
                    {message.sources.map((source, sourceIndex) => (
                      <div
                        key={`${source.protocol}-${source.step}-${sourceIndex}`}
                        className="mb-2 rounded-lg bg-slate-50 p-2 text-xs"
                      >
                        <p className="font-semibold">{source.step}</p>
                        <p className="text-slate-500">{source.protocol}</p>
                        {source.is_critical && (
                          <p className="mt-1 font-medium text-amber-700">
                            Critical step
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {message.needsClinicalTeam && (
                  <div className="mt-3 flex gap-2 rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-900">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                    <p>
                      Please confirm the correct instructions with the
                      patient's clinical team. Do not rely on an unanswered
                      or incomplete protocol.
                    </p>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="text-sm text-muted" role="status">
              Checking stored preparation instructions…
            </div>
          )}

          <div ref={endRef} />
        </div>

        {error && (
          <p role="alert" className="border-t border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </p>
        )}

        <div className="border-b border-line p-4">
          <label
            htmlFor="assistant-procedure"
            className="mb-2 block text-sm font-medium text-ink"
          >
            Procedure
          </label>

          <select
            id="assistant-procedure"
            value={procedureId}
            onChange={(event) => setProcedureId(event.target.value)}
            disabled={loadingProcedures || loading}
            className="w-full rounded-xl border border-line bg-white px-3 py-3 text-sm text-ink"
          >
            <option value="">
              {loadingProcedures ? "Loading procedures..." : "Select a procedure"}
            </option>

            {procedures.map((procedure) => (
              <option key={procedure.id} value={String(procedure.id)}>
                {procedure.patient.first_name} {procedure.patient.last_name}
                {" — "}
                {procedure.procedure_name}
                {" — "}
                {new Date(procedure.scheduled_at).toLocaleString()}
              </option>
            ))}
          </select>

          {!loadingProcedures && procedures.length === 0 && (
            <p className="mt-2 text-sm text-muted">
              No procedures are available. Create a procedure before asking
              preparation questions.
            </p>
          )}
        </div>

        <form onSubmit={sendQuestion} className="border-t border-line bg-white p-4">
          <label htmlFor="assistant-question" className="mb-2 block text-xs font-medium text-muted">
            Ask about preparation instructions
          </label>
          <div className="flex items-end gap-2">
            <textarea
              id="assistant-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              maxLength={1000}
              rows={2}
              placeholder="Type your question…"
              disabled={loading}
              className="min-h-[48px] min-w-0 flex-1 resize-y rounded-xl border border-line bg-white px-3 py-3 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/10 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={loading || !question.trim() || !procedureId}
              className="inline-flex h-12 shrink-0 items-center gap-2 rounded-xl bg-brand px-4 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <MessageCircle size={17} />
              Send
            </button>
          </div>
          <p className="mt-2 text-xs text-muted">
            This assistant does not replace personalized advice from your
            clinical team.
          </p>
        </form>
      </div>
    </section>
  );
}

function CreateProcedure({ onCreated, onCancel }) {
  const [patients, setPatients] = useState([]);
  const [protocols, setProtocols] = useState([]);
  const [patientId, setPatientId] = useState("");
  const [protocolId, setProtocolId] = useState("");
  const [procedureName, setProcedureName] = useState("");
  const [procedureDate, setProcedureDate] = useState("");
  const [hour, setHour] = useState("10");
  const [minute, setMinute] = useState("00");
  const [period, setPeriod] = useState("AM");
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadOptions() {
      try {
        const [patientResponse, protocolResponse] = await Promise.all([
          fetch("/api/patients/"),
          fetch("/api/protocols/"),
        ]);

        if (!patientResponse.ok || !protocolResponse.ok) {
          throw new Error("Unable to load patients or protocols.");
        }

        const patientData = await patientResponse.json();
        const protocolData = await protocolResponse.json();

        if (cancelled) return;

        setPatients(patientData.patients || []);

        const activeProtocols = (protocolData.protocols || []).filter(
          (protocol) => protocol.is_active && protocol.step_count > 0
        );

        setProtocols(activeProtocols);
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load form options.");
        }
      } finally {
        if (!cancelled) setLoadingOptions(false);
      }
    }

    loadOptions();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (
      !patientId ||
      !protocolId ||
      !procedureName.trim() ||
      !procedureDate ||
      !hour ||
      !minute ||
      !period
    ) {
      setError("Please complete every field.");
      return;
    }

    const hour24 = (Number(hour) % 12) + (period === "PM" ? 12 : 0);

    const scheduledAtIST =
      `${procedureDate}T${String(hour24).padStart(2, "0")}:${minute}`;

    const procedureDateUtc = istDateTimeToUtc(scheduledAtIST);

    if (!procedureDateUtc || Number.isNaN(procedureDateUtc.getTime())) {
      setError("Please enter a valid procedure date and time.");
      return;
    }

    if (procedureDateUtc <= new Date()) {
      setError("The procedure date and time must be in the future (IST).");
      return;
    }

    setSaving(true);

    try {
      const response = await fetch(
        "/api/procedures/",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
          },
          body: JSON.stringify({
            patient_id: Number(patientId),
            protocol_id: Number(protocolId),
            procedure_name: procedureName.trim(),
            scheduled_at: procedureDateUtc.toISOString(),
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Unable to create procedure.");
      }

      setSuccess(
        `Procedure created successfully. ${data.reminders_created} reminders scheduled.`
      );

      onCreated(data.procedure.id);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-6">
      <div>
        <p className="eyebrow">PROCEDURE MANAGEMENT</p>
        <h1 className="mt-2 text-2xl font-semibold text-ink">
          Create Procedure
        </h1>
        <p className="mt-2 text-sm text-muted">
          Register a procedure and schedule its preparation reminders.
        </p>
      </div>

      <div className="card max-w-3xl p-6 sm:p-8">
        {loadingOptions ? (
          <p className="text-sm text-muted">Loading patients and protocols...</p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="mb-2 block text-sm font-medium text-ink">
                Patient
              </label>
              <select
                value={patientId}
                onChange={(event) => setPatientId(event.target.value)}
                required
                className="w-full rounded-xl border border-line bg-white px-4 py-3 text-sm text-ink"
              >
                <option value="">Select a patient</option>
                {patients.map((patient) => (
                  <option key={patient.id} value={patient.id}>
                    {patient.first_name} {patient.last_name}
                  </option>
                ))}
              </select>
              {patients.length === 0 && (
                <p className="mt-2 text-xs text-amber-700">
                  No patients found. Add a patient to the database first.
                </p>
              )}
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-ink">
                Procedure name
              </label>
              <input
                type="text"
                value={procedureName}
                onChange={(event) => setProcedureName(event.target.value)}
                placeholder="e.g. Colonoscopy"
                maxLength={200}
                required
                className="w-full rounded-xl border border-line bg-white px-4 py-3 text-sm text-ink"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-ink">
                Preparation protocol
              </label>
              <select
                value={protocolId}
                onChange={(event) => setProtocolId(event.target.value)}
                required
                className="w-full rounded-xl border border-line bg-white px-4 py-3 text-sm text-ink"
              >
                <option value="">Select an active protocol</option>
                {protocols.map((protocol) => (
                  <option key={protocol.id} value={protocol.id}>
                    {protocol.name} ({protocol.step_count} steps)
                  </option>
                ))}
              </select>
              {protocols.length === 0 && (
                <p className="mt-2 text-xs text-amber-700">
                  No active protocols with preparation steps are available.
                </p>
              )}
            </div>

            <div className="space-y-3">
              <div>
                <label className="mb-2 block text-sm font-medium text-ink">
                  Procedure date (IST)
                </label>
                <input
                  type="date"
                  value={procedureDate}
                  onChange={(event) => setProcedureDate(event.target.value)}
                  min={getIstDateTimeLocalValue().slice(0, 10)}
                  required
                  className="w-full rounded-xl border border-line bg-white px-4 py-3 text-sm text-ink"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-ink">
                  Procedure time (IST)
                </label>

                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="mb-1 block text-xs text-muted">Hour</label>
                    <select
                      value={hour}
                      onChange={(event) => setHour(event.target.value)}
                      required
                      className="w-full rounded-xl border border-line bg-white px-3 py-3 text-sm text-ink"
                    >
                      {Array.from({ length: 12 }, (_, i) => String(i + 1)).map((h) => (
                        <option key={h} value={h.padStart(2, "0")}>
                          {h}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="mb-1 block text-xs text-muted">Minute</label>
                    <select
                      value={minute}
                      onChange={(event) => setMinute(event.target.value)}
                      required
                      className="w-full rounded-xl border border-line bg-white px-3 py-3 text-sm text-ink"
                    >
                      {Array.from({ length: 60 }, (_, i) => String(i).padStart(2, "0")).map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="mb-1 block text-xs text-muted">AM / PM</label>
                    <select
                      value={period}
                      onChange={(event) => setPeriod(event.target.value)}
                      required
                      className="w-full rounded-xl border border-line bg-white px-3 py-3 text-sm text-ink"
                    >
                      <option value="AM">AM</option>
                      <option value="PM">PM</option>
                    </select>
                  </div>
                </div>
              </div>

              <p className="text-xs text-muted">
                Enter the procedure time in India Standard Time (IST, UTC+05:30).
                Preparation reminders will be scheduled relative to this time.
              </p>
            </div>

            {error && (
              <div role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">
                {error}
              </div>
            )}

            {success && (
              <div role="status" className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700">
                {success}
              </div>
            )}

            <div className="flex flex-wrap gap-3 pt-2">
              <button
                type="submit"
                disabled={
                  saving ||
                  loadingOptions ||
                  patients.length === 0 ||
                  protocols.length === 0
                }
                className="rounded-xl bg-brand px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? "Creating procedure..." : "Create Procedure"}
              </button>

              <button
                type="button"
                onClick={onCancel}
                className="rounded-xl border border-line px-5 py-3 text-sm font-semibold text-ink hover:bg-slate-50"
              >
                Cancel
              </button>
            </div>

            <p className="text-xs leading-5 text-muted">
              This action creates database records and schedules reminders.
              It does not send WhatsApp messages. Verify all preparation
              instructions with the clinical team before using them for
              real patient care.
            </p>
          </form>
        )}
      </div>
    </section>
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
    <div className="flex min-h-screen bg-transparent">
      <Sidebar
        active={active}
        doctor={doctor}
        onNavigate={(page) => {
          setActive(page);
          if (page !== "Dashboard" && page !== "Create Procedure") {
            showToast(`${page} view is ready to connect to your workspace`);
          }
        }}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-[72px] items-center justify-between border-b border-line bg-[#fbfcff]/90 px-5 backdrop-blur sm:px-8">
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
          ) : active === "Create Procedure" ? (
            <CreateProcedure
              onCancel={() => setActive("Dashboard")}
              onCreated={(procedureId) => {
                setSelectedProcedureId(procedureId);
                setActive("Dashboard");
                showToast("Procedure created and reminders scheduled");
              }}
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
          ) : active === "Preparation Assistant" ? (
            <PreparationAssistant />
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
