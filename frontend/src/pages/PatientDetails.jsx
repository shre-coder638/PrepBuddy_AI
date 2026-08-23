import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import {
  ArrowLeft,
  ShieldCheck,
  User,
  CalendarDays,
  CheckCircle2,
  Clock3,
  MessageCircle,
  Bell,
  FileText,
  Phone,
  Mail,
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
    phone: "+91 98765 43210",
    email: "rahul@example.com",
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
    phone: "+91 98765 43211",
    email: "anjali@example.com",
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
    phone: "+91 98765 43212",
    email: "vikram@example.com",
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
    phone: "+91 98765 43213",
    email: "sneha@example.com",
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
    phone: "+91 98765 43214",
    email: "amit@example.com",
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
    phone: "+91 98765 43215",
    email: "neha@example.com",
  },
]

function PatientDetails() {
  const { id } = useParams()
  const [patient, setPatient] = useState(null)

  useEffect(() => {
    try {
      const savedPatients = JSON.parse(
        localStorage.getItem("prepbuddy_patients") || "[]"
      )

      const allPatients = [
        ...defaultPatients,
        ...(Array.isArray(savedPatients) ? savedPatients : []),
      ]

      const foundPatient = allPatients.find(
        (item) => item.id === id
      )

      setPatient(foundPatient || null)
    } catch (error) {
      console.error("Error loading patient:", error)
      setPatient(null)
    }
  }, [id])

  if (!patient) {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <div className="text-center">

          <h1 className="text-3xl font-bold">
            Patient Not Found
          </h1>

          <p className="mt-3 text-slate-500">
            No patient exists with ID: {id}
          </p>

          <Link
            to="/patients"
            className="mt-7 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold hover:bg-blue-500"
          >
            <ArrowLeft size={17} />
            Back to Patients
          </Link>

        </div>
      </div>
    )
  }

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

        <div className="mx-auto max-w-6xl p-6 lg:p-8">

          {/* BACK */}
          <Link
            to="/patients"
            className="mb-6 inline-flex items-center gap-2 text-sm text-slate-500 hover:text-blue-400"
          >
            <ArrowLeft size={16} />
            Back to Patients
          </Link>

          {/* PATIENT HEADER */}
          <div className="mb-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">

            <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">

              <div className="flex items-center gap-4">

                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-500/10 text-xl font-bold text-blue-400">
                  {patient.initials}
                </div>

                <div>

                  <div className="flex flex-wrap items-center gap-3">

                    <h1 className="text-3xl font-bold">
                      {patient.name}
                    </h1>

                    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
                      <CheckCircle2 size={13} />
                      {patient.status}
                    </span>

                  </div>

                  <p className="mt-1 text-sm text-slate-500">
                    Patient ID: {patient.id}
                  </p>

                </div>

              </div>

              <button
                type="button"
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-700 px-5 py-3 text-sm font-medium text-slate-300 hover:border-blue-500 hover:text-white"
              >
                <MessageCircle size={17} />
                Contact Patient
              </button>

            </div>

          </div>

          {/* TOP CARDS */}
          <div className="mb-6 grid gap-5 md:grid-cols-3">

            {/* PROCEDURE */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">

              <div className="mb-5 flex items-center gap-3">

                <div className="rounded-xl bg-blue-500/10 p-3 text-blue-400">
                  <CalendarDays size={20} />
                </div>

                <p className="text-sm text-slate-500">
                  Procedure
                </p>

              </div>

              <h2 className="text-lg font-bold">
                {patient.procedure}
              </h2>

              <p className="mt-1 text-xs text-slate-600">
                Scheduled procedure
              </p>

            </div>

            {/* DATE */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">

              <div className="mb-5 flex items-center gap-3">

                <div className="rounded-xl bg-purple-500/10 p-3 text-purple-400">
                  <CalendarDays size={20} />
                </div>

                <p className="text-sm text-slate-500">
                  Procedure Date
                </p>

              </div>

              <h2 className="text-lg font-bold">
                {patient.date}
              </h2>

              <p className="mt-1 text-xs text-slate-600">
                {patient.time}
              </p>

            </div>

            {/* PREPARATION */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">

              <div className="mb-5 flex items-center justify-between">

                <div className="flex items-center gap-3">

                  <div className="rounded-xl bg-emerald-500/10 p-3 text-emerald-400">
                    <CheckCircle2 size={20} />
                  </div>

                  <p className="text-sm text-slate-500">
                    Preparation
                  </p>

                </div>

                <span className="text-sm text-emerald-400">
                  {patient.status}
                </span>

              </div>

              <h2 className="text-2xl font-bold">
                {patient.progress}%
              </h2>

              <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-800">

                <div
                  className="h-full rounded-full bg-emerald-500"
                  style={{
                    width: `${patient.progress}%`,
                  }}
                />

              </div>

            </div>

          </div>

          {/* INFORMATION + QUICK ACTIONS */}
          <div className="grid gap-6 lg:grid-cols-3">

            {/* PATIENT INFORMATION */}
            <div className="lg:col-span-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">

              <div className="mb-6 flex items-center gap-3">

                <div className="rounded-xl bg-blue-500/10 p-3 text-blue-400">
                  <User size={20} />
                </div>

                <div>
                  <h2 className="font-bold">
                    Patient Information
                  </h2>

                  <p className="text-xs text-slate-500">
                    Basic patient details
                  </p>
                </div>

              </div>

              <div className="grid gap-6 md:grid-cols-2">

                <div>
                  <p className="text-xs text-slate-500">
                    Full Name
                  </p>

                  <p className="mt-2 font-medium">
                    {patient.name}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-slate-500">
                    Age
                  </p>

                  <p className="mt-2 font-medium">
                    {patient.age} years
                  </p>
                </div>

                <div>
                  <p className="text-xs text-slate-500">
                    Phone
                  </p>

                  <p className="mt-2 flex items-center gap-2 font-medium">
                    <Phone size={15} className="text-slate-500" />
                    {patient.phone || "Not provided"}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-slate-500">
                    Email
                  </p>

                  <p className="mt-2 flex items-center gap-2 font-medium">
                    <Mail size={15} className="text-slate-500" />
                    {patient.email || "Not provided"}
                  </p>
                </div>

              </div>

            </div>

            {/* QUICK ACTIONS */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">

              <h2 className="mb-5 font-bold">
                Quick Actions
              </h2>

              <div className="space-y-3">

                <button
                  type="button"
                  className="flex w-full items-center gap-3 rounded-xl border border-slate-800 p-4 text-left text-sm text-slate-300 hover:border-blue-500 hover:text-white"
                >
                  <Bell size={18} className="text-blue-400" />
                  Send Reminder
                </button>

                <button
                  type="button"
                  className="flex w-full items-center gap-3 rounded-xl border border-slate-800 p-4 text-left text-sm text-slate-300 hover:border-emerald-500 hover:text-white"
                >
                  <MessageCircle size={18} className="text-emerald-400" />
                  Send Message
                </button>

                <button
                  type="button"
                  className="flex w-full items-center gap-3 rounded-xl border border-slate-800 p-4 text-left text-sm text-slate-300 hover:border-purple-500 hover:text-white"
                >
                  <FileText size={18} className="text-purple-400" />
                  View Protocol
                </button>

              </div>

            </div>

          </div>

          {/* PREPARATION TIMELINE */}
          <div className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">

            <div className="flex items-center justify-between">

              <div>
                <h2 className="font-bold">
                  Preparation Timeline
                </h2>

                <p className="mt-1 text-xs text-slate-500">
                  Patient preparation milestones
                </p>
              </div>

              <span className="text-sm font-medium text-emerald-400">
                {patient.progress >= 80 ? "4 / 5 completed" : "2 / 5 completed"}
              </span>

            </div>

            <div className="mt-6 space-y-4">

              <div className="flex items-center gap-4">

                <div className="rounded-full bg-emerald-500/10 p-2 text-emerald-400">
                  <CheckCircle2 size={16} />
                </div>

                <div>
                  <p className="text-sm font-medium">
                    Preparation instructions reviewed
                  </p>

                  <p className="text-xs text-slate-600">
                    Completed
                  </p>
                </div>

              </div>

              <div className="flex items-center gap-4">

                <div className="rounded-full bg-emerald-500/10 p-2 text-emerald-400">
                  <CheckCircle2 size={16} />
                </div>

                <div>
                  <p className="text-sm font-medium">
                    Patient confirmation received
                  </p>

                  <p className="text-xs text-slate-600">
                    Completed
                  </p>
                </div>

              </div>

              <div className="flex items-center gap-4">

                <div className="rounded-full bg-blue-500/10 p-2 text-blue-400">
                  <Clock3 size={16} />
                </div>

                <div>
                  <p className="text-sm font-medium">
                    Final preparation check
                  </p>

                  <p className="text-xs text-slate-600">
                    In progress
                  </p>
                </div>

              </div>

            </div>

          </div>

        </div>

      </main>

    </div>
  )
}

export default PatientDetails