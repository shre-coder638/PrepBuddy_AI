import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

import {
  ShieldCheck,
  ArrowLeft,
  Search,
  Plus,
  Users,
  CheckCircle2,
  Clock3,
  AlertTriangle,
  ChevronRight,
  CalendarDays,
  Filter,
} from "lucide-react"

const defaultPatients = [
  {
    id: "PB-1024",
    initials: "RS",
    name: "Rahul Sharma",
    age: 42,
    procedure: "Colonoscopy",
    date: "Aug 24, 2026",
    time: "10:30 AM",
    progress: 92,
    status: "Ready",
  },
  {
    id: "PB-1025",
    initials: "AP",
    name: "Anjali Patel",
    age: 36,
    procedure: "Endoscopy",
    date: "Aug 24, 2026",
    time: "02:00 PM",
    progress: 64,
    status: "At Risk",
  },
  {
    id: "PB-1026",
    initials: "VK",
    name: "Vikram Kumar",
    age: 51,
    procedure: "Colonoscopy",
    date: "Aug 25, 2026",
    time: "09:00 AM",
    progress: 38,
    status: "Critical",
  },
  {
    id: "PB-1027",
    initials: "SM",
    name: "Sneha Mehta",
    age: 29,
    procedure: "Endoscopy",
    date: "Aug 25, 2026",
    time: "11:30 AM",
    progress: 81,
    status: "In Progress",
  },
  {
    id: "PB-1028",
    initials: "AM",
    name: "Amit Malhotra",
    age: 45,
    procedure: "Colonoscopy",
    date: "Aug 26, 2026",
    time: "09:30 AM",
    progress: 76,
    status: "In Progress",
  },
  {
    id: "PB-1029",
    initials: "NK",
    name: "Neha Kapoor",
    age: 33,
    procedure: "Endoscopy",
    date: "Aug 26, 2026",
    time: "01:00 PM",
    progress: 95,
    status: "Ready",
  },
]

function StatusBadge({ status }) {
  const config = {
    Ready: {
      icon: CheckCircle2,
      style: "bg-emerald-500/10 text-emerald-400",
    },
    "At Risk": {
      icon: Clock3,
      style: "bg-amber-500/10 text-amber-400",
    },
    Critical: {
      icon: AlertTriangle,
      style: "bg-red-500/10 text-red-400",
    },
    "In Progress": {
      icon: Clock3,
      style: "bg-blue-500/10 text-blue-400",
    },
  }

  const current = config[status] || config["In Progress"]
  const Icon = current.icon

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${current.style}`}
    >
      <Icon size={13} />
      {status}
    </span>
  )
}

function ProgressBar({ progress }) {
  let barColor = "bg-blue-500"

  if (progress >= 90) {
    barColor = "bg-emerald-500"
  } else if (progress < 50) {
    barColor = "bg-red-500"
  } else if (progress < 70) {
    barColor = "bg-amber-500"
  }

  return (
    <div className="flex items-center gap-3">
      <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full ${barColor}`}
          style={{ width: `${progress}%` }}
        />
      </div>

      <span className="text-xs text-slate-400">
        {progress}%
      </span>
    </div>
  )
}

function Patients() {
    const [searchTerm, setSearchTerm] = useState("")
    const [allPatients, setAllPatients] = useState(defaultPatients)
    const [statusFilter, setStatusFilter] = useState("All")
    const [showFilter, setShowFilter] = useState(false)

  // Load patients saved by AddPatient.jsx
  useEffect(() => {
    try {
      const savedPatients = JSON.parse(
        localStorage.getItem("prepbuddy_patients") || "[]"
      )

      if (Array.isArray(savedPatients)) {
        setAllPatients([...defaultPatients, ...savedPatients])
      }
    } catch (error) {
      console.error("Error loading patients:", error)
      setAllPatients(defaultPatients)
    }
  }, [])

  // Search patients
 const filteredPatients = allPatients.filter((patient) => {
  const search = searchTerm.toLowerCase().trim()

  const matchesSearch =
    !search ||
    patient.name?.toLowerCase().includes(search) ||
    patient.id?.toLowerCase().includes(search) ||
    patient.procedure?.toLowerCase().includes(search) ||
    patient.status?.toLowerCase().includes(search)

  const matchesStatus =
    statusFilter === "All" || patient.status === statusFilter

  return matchesSearch && matchesStatus
})

  // Dynamic statistics
  const totalPatients = allPatients.length

  const readyPatients = allPatients.filter(
    (patient) => patient.status === "Ready"
  ).length

  const atRiskPatients = allPatients.filter(
    (patient) => patient.status === "At Risk"
  ).length

  const criticalPatients = allPatients.filter(
    (patient) => patient.status === "Critical"
  ).length

  return (
    <div className="min-h-screen bg-slate-950 text-white">

      {/* HEADER */}
      <header className="fixed left-0 right-0 top-0 z-50 border-b border-slate-800 bg-slate-950/95 backdrop-blur">
        <div className="flex h-16 items-center justify-between px-6">

          <Link
            to="/clinic-dashboard"
            className="flex items-center gap-3"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600">
              <ShieldCheck size={22} />
            </div>

            <div>
              <h1 className="text-lg font-bold">
                PrepBuddy
              </h1>

              <p className="text-[10px] text-slate-500">
                Clinic Management
              </p>
            </div>
          </Link>

          <div className="flex items-center gap-3">

            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-600/20 text-sm font-semibold text-blue-400">
              CS
            </div>

            <div className="hidden sm:block">
              <p className="text-sm font-medium">
                Clinic Staff
              </p>

              <p className="text-xs text-slate-500">
                City Care Clinic
              </p>
            </div>

          </div>
        </div>
      </header>

      {/* MAIN */}
      <main className="pt-16">

        <div className="mx-auto max-w-7xl p-6 lg:p-8">

          {/* BACK */}
          <Link
            to="/clinic-dashboard"
            className="mb-6 inline-flex items-center gap-2 text-sm text-slate-500 transition hover:text-blue-400"
          >
            <ArrowLeft size={16} />
            Back to Dashboard
          </Link>

          {/* PAGE HEADING */}
          <div className="mb-8 flex flex-col gap-5 md:flex-row md:items-end md:justify-between">

            <div>

              <div className="mb-2 flex items-center gap-2 text-blue-400">
                <Users size={18} />

                <span className="text-sm font-medium">
                  Patient Management
                </span>
              </div>

              <h2 className="text-3xl font-bold tracking-tight">
                Patients
              </h2>

              <p className="mt-2 text-sm text-slate-500">
                View and monitor preparation progress for all patients.
              </p>

            </div>

            {/* ADD PATIENT */}
            <Link
              to="/add-patient"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold transition hover:bg-blue-500"
            >
              <Plus size={18} />
              Add Patient
            </Link>

          </div>

          {/* SUMMARY CARDS */}
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

            {/* TOTAL */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <div className="flex items-center justify-between">

                <div>
                  <p className="text-sm text-slate-500">
                    Total Patients
                  </p>

                  <p className="mt-2 text-2xl font-bold">
                    {totalPatients}
                  </p>
                </div>

                <div className="rounded-xl bg-blue-500/10 p-3 text-blue-400">
                  <Users size={20} />
                </div>

              </div>
            </div>

            {/* READY */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <div className="flex items-center justify-between">

                <div>
                  <p className="text-sm text-slate-500">
                    Ready
                  </p>

                  <p className="mt-2 text-2xl font-bold">
                    {readyPatients}
                  </p>
                </div>

                <div className="rounded-xl bg-emerald-500/10 p-3 text-emerald-400">
                  <CheckCircle2 size={20} />
                </div>

              </div>
            </div>

            {/* AT RISK */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <div className="flex items-center justify-between">

                <div>
                  <p className="text-sm text-slate-500">
                    At Risk
                  </p>

                  <p className="mt-2 text-2xl font-bold">
                    {atRiskPatients}
                  </p>
                </div>

                <div className="rounded-xl bg-amber-500/10 p-3 text-amber-400">
                  <Clock3 size={20} />
                </div>

              </div>
            </div>

            {/* CRITICAL */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <div className="flex items-center justify-between">

                <div>
                  <p className="text-sm text-slate-500">
                    Critical
                  </p>

                  <p className="mt-2 text-2xl font-bold">
                    {criticalPatients}
                  </p>
                </div>

                <div className="rounded-xl bg-red-500/10 p-3 text-red-400">
                  <AlertTriangle size={20} />
                </div>

              </div>
            </div>

          </div>

          {/* PATIENT LIST */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60">

            {/* TOOLBAR */}
            <div className="flex flex-col gap-4 border-b border-slate-800 p-5 lg:flex-row lg:items-center lg:justify-between">

              <div>
                <h3 className="font-semibold">
                  All Patients
                </h3>

                <p className="mt-1 text-xs text-slate-500">
                  {filteredPatients.length} patients found
                </p>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row">

                {/* SEARCH */}
                <div className="relative">

                  <Search
                    size={17}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600"
                  />

                  <input
                    type="text"
                    placeholder="Search patient..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full rounded-lg border border-slate-800 bg-slate-950 py-2.5 pl-10 pr-4 text-sm text-white outline-none placeholder:text-slate-600 focus:border-blue-500 sm:w-64"
                  />

                </div>

                {/* FILTER */}
                <div className="relative">
                    <button
                    type="button"
                    onClick={() => setShowFilter(!showFilter)}
                    className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-800 bg-slate-950 px-4 py-2.5 text-sm text-slate-400 transition hover:border-slate-600 hover:text-white">
                        <Filter size={16} />
                        Filter
                        </button>
                        
                        {showFilter && (
                            <div className="absolute right-0 top-12 z-50 w-44 rounded-xl border border-slate-800 bg-slate-900 p-2 shadow-xl">
                                
                                {["All", "Ready", "In Progress", "At Risk", "Critical"].map(
                                    (status) => (
                                    <button
                                    key={status}
                                    type="button"
                                    onClick={() => {
                                        setStatusFilter(status)
                                        setShowFilter(false) }}
            className={`w-full rounded-lg px-3 py-2 text-left text-sm transition ${
              statusFilter === status
                ? "bg-blue-600 text-white"
                : "text-slate-400 hover:bg-slate-800 hover:text-white"
            }`}
          >
            {status}
          </button>
        )
      )}

    </div>
  )}
</div>

              </div>

            </div>

            {/* TABLE */}
            <div className="overflow-x-auto">

              <table className="w-full min-w-[1000px]">

                <thead>
                  <tr className="border-b border-slate-800 text-left text-xs text-slate-500">

                    <th className="px-5 py-4 font-medium">
                      Patient
                    </th>

                    <th className="px-5 py-4 font-medium">
                      Procedure
                    </th>

                    <th className="px-5 py-4 font-medium">
                      Procedure Date
                    </th>

                    <th className="px-5 py-4 font-medium">
                      Preparation
                    </th>

                    <th className="px-5 py-4 font-medium">
                      Status
                    </th>

                    <th className="px-5 py-4 text-right font-medium">
                      Action
                    </th>

                  </tr>
                </thead>

                <tbody>

                  {filteredPatients.length > 0 ? (

                    filteredPatients.map((patient) => (

                      <tr
                        key={patient.id}
                        className="border-b border-slate-800/70 transition hover:bg-slate-800/30"
                      >

                        {/* PATIENT */}
                        <td className="px-5 py-4">

                          <div className="flex items-center gap-3">

                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/10 text-xs font-semibold text-blue-400">
                              {patient.initials}
                            </div>

                            <div>

                              <p className="text-sm font-medium">
                                {patient.name}
                              </p>

                              <p className="mt-0.5 text-xs text-slate-600">
                                {patient.id} • Age {patient.age}
                              </p>

                            </div>

                          </div>

                        </td>

                        {/* PROCEDURE */}
                        <td className="px-5 py-4">

                          <div className="flex items-center gap-2">

                            <CalendarDays
                              size={15}
                              className="text-slate-600"
                            />

                            <span className="text-sm text-slate-300">
                              {patient.procedure}
                            </span>

                          </div>

                        </td>

                        {/* DATE */}
                        <td className="px-5 py-4">

                          <p className="text-sm text-slate-300">
                            {patient.date}
                          </p>

                          <p className="mt-0.5 text-xs text-slate-600">
                            {patient.time}
                          </p>

                        </td>

                        {/* PROGRESS */}
                        <td className="px-5 py-4">

                          <ProgressBar
                            progress={patient.progress}
                          />

                        </td>

                        {/* STATUS */}
                        <td className="px-5 py-4">

                          <StatusBadge
                            status={patient.status}
                          />

                        </td>

                        {/* ACTION */}
                        <td className="px-5 py-4 text-right">

                          <Link
                            to={`/patient/${patient.id}`}
                            className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 transition hover:text-blue-400"
                          >
                            View
                            <ChevronRight size={15} />
                          </Link>

                        </td>

                      </tr>

                    ))

                  ) : (

                    <tr>

                      <td
                        colSpan="6"
                        className="px-5 py-12 text-center"
                      >

                        <div className="flex flex-col items-center">

                          <Search
                            size={32}
                            className="mb-3 text-slate-700"
                          />

                          <p className="font-medium text-slate-400">
                            No patients found
                          </p>

                          <p className="mt-1 text-xs text-slate-600">
                            Try searching with another name or patient ID.
                          </p>

                        </div>

                      </td>

                    </tr>

                  )}

                </tbody>

              </table>

            </div>

            {/* FOOTER */}
            <div className="flex flex-col gap-3 border-t border-slate-800 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">

              <p className="text-xs text-slate-600">
                Showing {filteredPatients.length} of {allPatients.length} patients
              </p>

              <div className="flex items-center gap-2">

                <button
                  type="button"
                  className="rounded-lg border border-slate-800 px-3 py-1.5 text-xs text-slate-600"
                >
                  Previous
                </button>

                <button
                  type="button"
                  className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white"
                >
                  1
                </button>

                <button
                  type="button"
                  className="rounded-lg border border-slate-800 px-3 py-1.5 text-xs text-slate-400 hover:border-slate-600"
                >
                  2
                </button>

                <button
                  type="button"
                  className="rounded-lg border border-slate-800 px-3 py-1.5 text-xs text-slate-400 hover:border-slate-600"
                >
                  3
                </button>

                <button
                  type="button"
                  className="rounded-lg border border-slate-800 px-3 py-1.5 text-xs text-slate-400 hover:border-slate-600"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default Patients