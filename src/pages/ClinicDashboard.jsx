import { Link } from "react-router-dom"
import {
  ShieldCheck,
  LayoutDashboard,
  Users,
  CalendarDays,
  ClipboardList,
  BellRing,
  AlertTriangle,
  MessageCircle,
  Settings,
  Search,
  CheckCircle2,
  Clock3,
  LogOut,
  ChevronRight,
} from "lucide-react"

function ClinicDashboard() {
  return (
    <div className="min-h-screen bg-slate-950 text-white">

      {/* ================= HEADER ================= */}
      <header className="fixed left-0 right-0 top-0 z-50 border-b border-slate-800 bg-slate-950/95 backdrop-blur">
        <div className="flex h-16 items-center justify-between px-6">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-3">
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

          {/* Profile */}
          <div className="flex items-center gap-4">

            <button className="relative rounded-lg p-2 text-slate-400 transition hover:bg-slate-800 hover:text-white">
              <BellRing size={19} />

              <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-red-500" />
            </button>

            <div className="hidden h-8 w-px bg-slate-800 sm:block" />

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

        </div>
      </header>


      {/* ================= SIDEBAR ================= */}
      <aside className="fixed bottom-0 left-0 top-16 hidden w-64 border-r border-slate-800 bg-slate-950 lg:flex lg:flex-col">

        <nav className="flex-1 space-y-1 p-4">

          <p className="mb-3 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-600">
            Main Menu
          </p>

          {/* Dashboard */}
          <button className="flex w-full items-center gap-3 rounded-xl bg-blue-600/10 px-3 py-3 text-sm font-medium text-blue-400">
            <LayoutDashboard size={19} />
            Dashboard
          </button>

          {/* Patients */}
          <Link
          to="/patients"
          className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white">
            <Users size={19} />
            Patients
            </Link>

          {/* Procedures */}
          <button className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white">
            <CalendarDays size={19} />
            Procedures
          </button>

          {/* Protocols */}
          <button className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white">
            <ClipboardList size={19} />
            Protocols
          </button>

          {/* Reminders */}
          <button className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white">
            <BellRing size={19} />
            Reminders
          </button>

          {/* Alerts */}
          <button className="flex w-full items-center justify-between rounded-xl px-3 py-3 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white">

            <span className="flex items-center gap-3">
              <AlertTriangle size={19} />
              Alerts
            </span>

            <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold text-red-400">
              7
            </span>

          </button>

          {/* AI Assistant */}
          <button className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white">
            <MessageCircle size={19} />
            AI Assistant
          </button>

          <div className="my-4 border-t border-slate-800" />

          <p className="mb-3 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-600">
            Account
          </p>

          {/* Settings */}
          <button className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white">
            <Settings size={19} />
            Settings
          </button>

        </nav>

        {/* Logout */}
        <div className="border-t border-slate-800 p-4">

          <Link
            to="/login"
            className="flex items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white"
          >
            <LogOut size={19} />
            Logout
          </Link>

        </div>

      </aside>


      {/* ================= MAIN CONTENT ================= */}
      <main className="pt-16 lg:pl-64">

        <div className="mx-auto max-w-7xl p-6 lg:p-8">

          {/* Welcome */}
          <div className="mb-8">

            <p className="mb-1 text-sm text-blue-400">
              Sunday, August 23, 2026
            </p>

            <h2 className="text-3xl font-bold tracking-tight">
              Good evening, Clinic Staff
            </h2>

            <p className="mt-2 text-sm text-slate-500">
              Here's an overview of today's patient preparation.
            </p>

          </div>

          {/* ================= STAT CARDS ================= */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

            {/* Total Patients */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">

              <div className="flex items-start justify-between">

                <div>
                  <p className="text-sm text-slate-500">
                    Total Patients
                  </p>

                  <p className="mt-2 text-3xl font-bold">
                    72
                  </p>
                </div>

                <div className="rounded-xl bg-blue-500/10 p-3 text-blue-400">
                  <Users size={21} />
                </div>

              </div>

              <p className="mt-4 text-xs text-slate-500">
                Patients with upcoming procedures
              </p>

            </div>

            {/* Ready */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">

              <div className="flex items-start justify-between">

                <div>
                  <p className="text-sm text-slate-500">
                    Ready
                  </p>

                  <p className="mt-2 text-3xl font-bold">
                    47
                  </p>
                </div>

                <div className="rounded-xl bg-emerald-500/10 p-3 text-emerald-400">
                  <CheckCircle2 size={21} />
                </div>

              </div>

              <p className="mt-4 text-xs text-emerald-400">
                65.3% preparation completed
              </p>

            </div>


            {/* At Risk */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">

              <div className="flex items-start justify-between">

                <div>
                  <p className="text-sm text-slate-500">
                    At Risk
                  </p>

                  <p className="mt-2 text-3xl font-bold">
                    18
                  </p>
                </div>

                <div className="rounded-xl bg-amber-500/10 p-3 text-amber-400">
                  <Clock3 size={21} />
                </div>

              </div>

              <p className="mt-4 text-xs text-amber-400">
                Require attention
              </p>

            </div>


            {/* Critical Alerts */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">

              <div className="flex items-start justify-between">

                <div>
                  <p className="text-sm text-slate-500">
                    Critical Alerts
                  </p>

                  <p className="mt-2 text-3xl font-bold">
                    7
                  </p>
                </div>

                <div className="rounded-xl bg-red-500/10 p-3 text-red-400">
                  <AlertTriangle size={21} />
                </div>

              </div>

              <p className="mt-4 text-xs text-red-400">
                Need immediate follow-up
              </p>

            </div>

          </div>


          {/* ================= PATIENT TABLE ================= */}
          <div className="mt-8 rounded-2xl border border-slate-800 bg-slate-900/60">

            {/* Table Header */}
            <div className="flex flex-col gap-4 border-b border-slate-800 p-5 md:flex-row md:items-center md:justify-between">

              <div>
                <h3 className="font-semibold">
                  Patient Preparation Status
                </h3>

                <p className="mt-1 text-xs text-slate-500">
                  Monitor upcoming procedures and preparation progress.
                </p>
              </div>

              <div className="flex items-center gap-3">

                {/* Search */}
                <div className="relative">

                  <Search
                    size={16}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600"
                  />

                  <input
                    type="text"
                    placeholder="Search patient..."
                    className="w-48 rounded-lg border border-slate-800 bg-slate-950 py-2 pl-9 pr-3 text-xs text-white outline-none placeholder:text-slate-600 focus:border-blue-500"
                  />

                </div>

               <Link
               to="/patients"
               className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 transition hover:border-blue-500">
                View All
                </Link>

              </div>

            </div>


            {/* Table */}
            <div className="overflow-x-auto">

              <table className="w-full min-w-[800px]">

                <thead>
                  <tr className="border-b border-slate-800 text-left text-xs text-slate-500">

                    <th className="px-5 py-4 font-medium">
                      Patient
                    </th>

                    <th className="px-5 py-4 font-medium">
                      Procedure
                    </th>

                    <th className="px-5 py-4 font-medium">
                      Date & Time
                    </th>

                    <th className="px-5 py-4 font-medium">
                      Preparation
                    </th>

                    <th className="px-5 py-4 font-medium">
                      Status
                    </th>

                    <th className="px-5 py-4 font-medium">
                      Action
                    </th>

                  </tr>
                </thead>

                <tbody>

                  {/* Patient 1 */}
                  <tr className="border-b border-slate-800/70 transition hover:bg-slate-800/30">

                    <td className="px-5 py-4">

                      <div className="flex items-center gap-3">

                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-500/10 text-xs font-semibold text-blue-400">
                          RS
                        </div>

                        <div>
                          <p className="text-sm font-medium">
                            Rahul Sharma
                          </p>

                          <p className="text-xs text-slate-600">
                            ID: PB-1024
                          </p>
                        </div>

                      </div>

                    </td>

                    <td className="px-5 py-4 text-sm text-slate-300">
                      Colonoscopy
                    </td>

                    <td className="px-5 py-4">

                      <p className="text-sm text-slate-300">
                        Aug 24, 2026
                      </p>

                      <p className="text-xs text-slate-600">
                        10:30 AM
                      </p>

                    </td>

                    <td className="px-5 py-4">

                      <div className="flex items-center gap-3">

                        <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-800">
                          <div className="h-full w-[92%] rounded-full bg-emerald-500" />
                        </div>

                        <span className="text-xs text-slate-400">
                          92%
                        </span>

                      </div>

                    </td>

                    <td className="px-5 py-4">

                      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-400">
                        <CheckCircle2 size={13} />
                        Ready
                      </span>

                    </td>

                    <td className="px-5 py-4">

                      <button className="text-slate-500 transition hover:text-blue-400">
                        <ChevronRight size={18} />
                      </button>

                    </td>

                  </tr>


                  {/* Patient 2 */}
                  <tr className="border-b border-slate-800/70 transition hover:bg-slate-800/30">

                    <td className="px-5 py-4">

                      <div className="flex items-center gap-3">

                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-purple-500/10 text-xs font-semibold text-purple-400">
                          AP
                        </div>

                        <div>
                          <p className="text-sm font-medium">
                            Anjali Patel
                          </p>

                          <p className="text-xs text-slate-600">
                            ID: PB-1025
                          </p>
                        </div>

                      </div>

                    </td>

                    <td className="px-5 py-4 text-sm text-slate-300">
                      Endoscopy
                    </td>

                    <td className="px-5 py-4">

                      <p className="text-sm text-slate-300">
                        Aug 24, 2026
                      </p>

                      <p className="text-xs text-slate-600">
                        02:00 PM
                      </p>

                    </td>

                    <td className="px-5 py-4">

                      <div className="flex items-center gap-3">

                        <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-800">
                          <div className="h-full w-[64%] rounded-full bg-amber-500" />
                        </div>

                        <span className="text-xs text-slate-400">
                          64%
                        </span>

                      </div>

                    </td>

                    <td className="px-5 py-4">

                      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-400">
                        <Clock3 size={13} />
                        At Risk
                      </span>

                    </td>

                    <td className="px-5 py-4">

                      <button className="text-slate-500 transition hover:text-blue-400">
                        <ChevronRight size={18} />
                      </button>

                    </td>

                  </tr>


                  {/* Patient 3 */}
                  <tr className="border-b border-slate-800/70 transition hover:bg-slate-800/30">

                    <td className="px-5 py-4">

                      <div className="flex items-center gap-3">

                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-red-500/10 text-xs font-semibold text-red-400">
                          VK
                        </div>

                        <div>
                          <p className="text-sm font-medium">
                            Vikram Kumar
                          </p>

                          <p className="text-xs text-slate-600">
                            ID: PB-1026
                          </p>
                        </div>

                      </div>

                    </td>

                    <td className="px-5 py-4 text-sm text-slate-300">
                      Colonoscopy
                    </td>

                    <td className="px-5 py-4">

                      <p className="text-sm text-slate-300">
                        Aug 25, 2026
                      </p>

                      <p className="text-xs text-slate-600">
                        09:00 AM
                      </p>

                    </td>

                    <td className="px-5 py-4">

                      <div className="flex items-center gap-3">

                        <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-800">
                          <div className="h-full w-[38%] rounded-full bg-red-500" />
                        </div>

                        <span className="text-xs text-slate-400">
                          38%
                        </span>

                      </div>

                    </td>

                    <td className="px-5 py-4">

                      <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-400">
                        <AlertTriangle size={13} />
                        Critical
                      </span>

                    </td>

                    <td className="px-5 py-4">

                      <button className="text-slate-500 transition hover:text-blue-400">
                        <ChevronRight size={18} />
                      </button>

                    </td>

                  </tr>


                  {/* Patient 4 */}
                  <tr className="transition hover:bg-slate-800/30">

                    <td className="px-5 py-4">

                      <div className="flex items-center gap-3">

                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-500/10 text-xs font-semibold text-cyan-400">
                          SM
                        </div>

                        <div>
                          <p className="text-sm font-medium">
                            Sneha Mehta
                          </p>

                          <p className="text-xs text-slate-600">
                            ID: PB-1027
                          </p>
                        </div>

                      </div>

                    </td>

                    <td className="px-5 py-4 text-sm text-slate-300">
                      Endoscopy
                    </td>

                    <td className="px-5 py-4">

                      <p className="text-sm text-slate-300">
                        Aug 25, 2026
                      </p>

                      <p className="text-xs text-slate-600">
                        11:30 AM
                      </p>

                    </td>

                    <td className="px-5 py-4">

                      <div className="flex items-center gap-3">

                        <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-800">
                          <div className="h-full w-[81%] rounded-full bg-blue-500" />
                        </div>

                        <span className="text-xs text-slate-400">
                          81%
                        </span>

                      </div>

                    </td>

                    <td className="px-5 py-4">

                      <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-2.5 py-1 text-xs font-medium text-blue-400">
                        <Clock3 size={13} />
                        In Progress
                      </span>

                    </td>

                    <td className="px-5 py-4">

                      <button className="text-slate-500 transition hover:text-blue-400">
                        <ChevronRight size={18} />
                      </button>

                    </td>

                  </tr>

                </tbody>

              </table>

            </div>

          </div>


          {/* ================= BOTTOM SECTION ================= */}
          <div className="mt-6 grid gap-6 lg:grid-cols-2">

            {/* Alerts */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">

              <div className="mb-5 flex items-center justify-between">

                <div>
                  <h3 className="font-semibold">
                    Recent Alerts
                  </h3>

                  <p className="mt-1 text-xs text-slate-500">
                    Patients requiring attention
                  </p>
                </div>

                <button className="text-xs text-blue-400 hover:text-blue-300">
                  View all
                </button>

              </div>


              <div className="space-y-3">

                <div className="flex items-start gap-3 rounded-xl border border-red-500/10 bg-red-500/5 p-3">

                  <AlertTriangle
                    size={18}
                    className="mt-0.5 text-red-400"
                  />

                  <div className="flex-1">

                    <p className="text-sm font-medium">
                      Vikram Kumar
                    </p>

                    <p className="mt-1 text-xs text-slate-500">
                      Critical preparation step not confirmed.
                    </p>

                  </div>

                  <span className="text-[10px] text-slate-600">
                    12m
                  </span>

                </div>


                <div className="flex items-start gap-3 rounded-xl border border-amber-500/10 bg-amber-500/5 p-3">

                  <Clock3
                    size={18}
                    className="mt-0.5 text-amber-400"
                  />

                  <div className="flex-1">

                    <p className="text-sm font-medium">
                      Anjali Patel
                    </p>

                    <p className="mt-1 text-xs text-slate-500">
                      Preparation milestone is overdue.
                    </p>

                  </div>

                  <span className="text-[10px] text-slate-600">
                    28m
                  </span>

                </div>


                <div className="flex items-start gap-3 rounded-xl border border-blue-500/10 bg-blue-500/5 p-3">

                  <MessageCircle
                    size={18}
                    className="mt-0.5 text-blue-400"
                  />

                  <div className="flex-1">

                    <p className="text-sm font-medium">
                      Rahul Sharma
                    </p>

                    <p className="mt-1 text-xs text-slate-500">
                      Patient confirmed latest preparation step.
                    </p>

                  </div>

                  <span className="text-[10px] text-slate-600">
                    1h
                  </span>

                </div>

              </div>

            </div>


            {/* Today's Activity */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">

              <div className="mb-5">

                <h3 className="font-semibold">
                  Today's Activity
                </h3>

                <p className="mt-1 text-xs text-slate-500">
                  Recent preparation updates
                </p>

              </div>

              <div className="space-y-4">

                <div className="flex gap-3">

                  <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400">
                    <CheckCircle2 size={14} />
                  </div>

                  <div>
                    <p className="text-sm">
                      Preparation confirmed
                    </p>

                    <p className="text-xs text-slate-600">
                      Rahul Sharma • 9:42 PM
                    </p>
                  </div>

                </div>

                <div className="flex gap-3">

                  <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-500/10 text-amber-400">
                    <Clock3 size={14} />
                  </div>

                  <div>
                    <p className="text-sm">
                      Reminder sent
                    </p>

                    <p className="text-xs text-slate-600">
                      Anjali Patel • 9:20 PM
                    </p>
                  </div>

                </div>

                <div className="flex gap-3">

                  <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-red-500/10 text-red-400">
                    <AlertTriangle size={14} />
                  </div>

                  <div>
                    <p className="text-sm">
                      Critical milestone missed
                    </p>

                    <p className="text-xs text-slate-600">
                      Vikram Kumar • 8:55 PM
                    </p>
                  </div>

                </div>

                <div className="flex gap-3">

                  <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-500/10 text-blue-400">
                    <Users size={14} />
                  </div>

                  <div>
                    <p className="text-sm">
                      New patient added
                    </p>

                    <p className="text-xs text-slate-600">
                      Sneha Mehta • 8:30 PM
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default ClinicDashboard