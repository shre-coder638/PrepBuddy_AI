import { BrowserRouter, Routes, Route } from "react-router-dom"

import Landing from "./pages/landing"
import Login from "./pages/Login"
import Register from "./pages/Register"
import ClinicDashboard from "./pages/ClinicDashboard"
import Patients from "./pages/Patients"
import PatientDetails from "./pages/PatientDetails"
import AddPatient from "./pages/AddPatient"

function App() {
  return (
    <BrowserRouter>
      <Routes>

        <Route path="/" element={<Landing />} />

        <Route path="/login" element={<Login />} />

        <Route path="/register" element={<Register />} />

        <Route
          path="/clinic-dashboard"
          element={<ClinicDashboard />}
        />

        <Route
          path="/patients"
          element={<Patients />}
        />

        <Route
          path="/patient/:id"
          element={<PatientDetails />}
        />

        <Route
          path="/add-patient"
          element={<AddPatient />}
        />

      </Routes>
    </BrowserRouter>
  )
}

export default App