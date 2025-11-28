import React, { useState, useCallback } from 'react';
import { Calendar, Clock, Users, CheckCircle, AlertCircle, Zap } from 'lucide-react';

// ============================================================================
// MOTEUR DE GESTION DES RÉSERVATIONS
// ============================================================================

class ReservationEngine {
  constructor() {
    this.slots = this.initializeSlots();
    this.reservations = {};
  }

  initializeSlots() {
    const slots = {};
    const hours = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00', '20:00'];
    const maxCapacity = 4;

    hours.forEach(hour => {
      slots[hour] = { capacity: maxCapacity, booked: 0, available: maxCapacity };
    });
    return slots;
  }

  getAvailableSlots(date) {
    if (!this.reservations[date]) {
      this.reservations[date] = { ...this.slots };
    }
    return this.reservations[date];
  }

  isSlotAvailable(date, time) {
    const daySlots = this.getAvailableSlots(date);
    return daySlots[time] && daySlots[time].available > 0;
  }

  reserveSlot(date, time, clientName, partySize = 1) {
    const daySlots = this.getAvailableSlots(date);
    
    if (!daySlots[time]) return { success: false, error: 'Créneau invalide' };
    if (daySlots[time].available < partySize) {
      return { success: false, error: `Pas assez de places (${daySlots[time].available} disponible(s))` };
    }

    daySlots[time].booked += partySize;
    daySlots[time].available -= partySize;
    
    return { success: true, time, date, clientName, partySize };
  }

  getReservationsForDay(date) {
    return Object.entries(this.getAvailableSlots(date)).map(([time, slot]) => ({
      time,
      booked: slot.booked,
      capacity: slot.capacity,
      available: slot.available
    }));
  }

  resetDay(date) {
    this.reservations[date] = this.initializeSlots();
  }
}

// ============================================================================
// AGENT IA - RAISONNEMENT ET PRISE DE DÉCISION
// ============================================================================

class IntelligentAgent {
  constructor(engine) {
    this.engine = engine;
  }

  // Analyse les créneaux et propose les meilleures alternatives
  analyzeSlotsIntelligently(date, requestedTime, partySize) {
    const slots = this.engine.getAvailableSlots(date);
    const availableSlots = Object.entries(slots)
      .filter(([_, slot]) => slot.available >= partySize)
      .map(([time, slot]) => ({
        time,
        available: slot.available,
        score: this.calculateSlotScore(time, slot, requestedTime)
      }))
      .sort((a, b) => b.score - a.score);

    return availableSlots;
  }

  // Scoring intelligent des créneaux
  calculateSlotScore(time, slot, requestedTime) {
    const requestedHour = parseInt(requestedTime.split(':')[0]);
    const slotHour = parseInt(time.split(':')[0]);
    
    const timeDifference = Math.abs(slotHour - requestedHour);
    const availabilityFactor = slot.available / slot.capacity;
    
    // Favorise les créneaux proches et avec plus de disponibilité
    const proximityScore = Math.max(0, 10 - timeDifference);
    const availabilityScore = availabilityFactor * 5;
    
    return proximityScore + availabilityScore;
  }

  // Décision intelligente : réserver ou proposer alternative
  makeDecision(date, time, clientName, partySize) {
    // Tentative de réservation au créneau demandé
    const reservation = this.engine.reserveSlot(date, time, clientName, partySize);
    
    if (reservation.success) {
      return {
        action: 'RESERVED',
        message: `✓ Réservation confirmée pour ${clientName} à ${time}`,
        data: reservation,
        alternative: null
      };
    }

    // Si indisponible, analyser et proposer alternatives
    const alternatives = this.analyzeSlotsIntelligently(date, time, partySize);
    
    if (alternatives.length > 0) {
      const bestAlternative = alternatives[0];
      const altReservation = this.engine.reserveSlot(date, bestAlternative.time, clientName, partySize);
      
      if (altReservation.success) {
        return {
          action: 'ALTERNATIVE_PROPOSED',
          message: `Créneau ${time} complet. Alternative proposée : ${bestAlternative.time}`,
          data: altReservation,
          alternative: {
            time: bestAlternative.time,
            reason: `Plus proche disponibilité (${bestAlternative.available} places)`
          }
        };
      }
    }

    return {
      action: 'FAILED',
      message: `Impossible de réserver à ${time}. Aucun créneau disponible pour ${partySize} personne(s).`,
      data: null,
      alternative: null
    };
  }
}

// ============================================================================
// INTERFACE UTILISATEUR
// ============================================================================

export default function ReservationApp() {
  const engineRef = React.useRef(new ReservationEngine());
  const agentRef = React.useRef(new IntelligentAgent(engineRef.current));

  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedTime, setSelectedTime] = useState('12:00');
  const [clientName, setClientName] = useState('');
  const [partySize, setPartySize] = useState('2');
  const [message, setMessage] = useState('');
  const [reservationResult, setReservationResult] = useState(null);
  const [dayReservations, setDayReservations] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);

  // Récupérer les réservations du jour
  const updateDayReservations = useCallback((date) => {
    const reservations = engineRef.current.getReservationsForDay(date);
    setDayReservations(reservations);
  }, []);

  // Initialiser à la première charge
  React.useEffect(() => {
    updateDayReservations(selectedDate);
  }, []);

  // Mettre à jour quand la date change
  const handleDateChange = (e) => {
    const newDate = e.target.value;
    setSelectedDate(newDate);
    updateDayReservations(newDate);
    setReservationResult(null);
    setMessage('');
  };

  // Traiter une réservation
  const handleReserve = async () => {
    if (!clientName.trim()) {
      setMessage('⚠️ Veuillez entrer votre nom');
      return;
    }

    setIsProcessing(true);
    
    // Simulation d'un délai d'IA (< 1 seconde)
    setTimeout(() => {
      const decision = agentRef.current.makeDecision(
        selectedDate,
        selectedTime,
        clientName,
        parseInt(partySize)
      );

      setReservationResult(decision);
      setMessage(decision.message);
      updateDayReservations(selectedDate);
      
      if (decision.action === 'RESERVED' || decision.action === 'ALTERNATIVE_PROPOSED') {
        setClientName('');
      }
      
      setIsProcessing(false);
    }, 300);
  };

  const getMessageIcon = () => {
    if (!reservationResult) return null;
    if (reservationResult.action === 'FAILED') return <AlertCircle className="w-5 h-5 text-red-500" />;
    return <CheckCircle className="w-5 h-5 text-green-500" />;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Zap className="w-8 h-8 text-purple-600" />
            <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
              Réservation Intelligente
            </h1>
          </div>
          <p className="text-gray-600 ml-11">Système d'agent IA autonome pour la gestion des disponibilités</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Formulaire de réservation */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-2xl shadow-lg p-8 border border-purple-100">
              <h2 className="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
                <Calendar className="w-6 h-6 text-purple-600" />
                Nouvelle Réservation
              </h2>

              {/* Date */}
              <div className="mb-6">
                <label className="block text-sm font-semibold text-gray-700 mb-2">Date</label>
                <input
                  type="date"
                  value={selectedDate}
                  onChange={handleDateChange}
                  className="w-full px-4 py-3 border-2 border-purple-200 rounded-lg focus:border-purple-500 focus:outline-none transition"
                />
              </div>

              {/* Créneau horaire */}
              <div className="mb-6">
                <label className="block text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  Créneau souhaité
                </label>
                <select
                  value={selectedTime}
                  onChange={(e) => setSelectedTime(e.target.value)}
                  className="w-full px-4 py-3 border-2 border-purple-200 rounded-lg focus:border-purple-500 focus:outline-none transition"
                >
                  {Object.keys(dayReservations.length > 0 ? dayReservations.reduce((acc, r) => ({ ...acc, [r.time]: true }), {}) : {}).sort().map(time => (
                    <option key={time} value={time}>{time}</option>
                  ))}
                </select>
              </div>

              {/* Nombre de personnes */}
              <div className="mb-6">
                <label className="block text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                  <Users className="w-4 h-4" />
                  Nombre de personnes
                </label>
                <input
                  type="number"
                  min="1"
                  max="8"
                  value={partySize}
                  onChange={(e) => setPartySize(e.target.value)}
                  className="w-full px-4 py-3 border-2 border-purple-200 rounded-lg focus:border-purple-500 focus:outline-none transition"
                />
              </div>

              {/* Nom du client */}
              <div className="mb-8">
                <label className="block text-sm font-semibold text-gray-700 mb-2">Votre nom</label>
                <input
                  type="text"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  placeholder="Entrez votre nom"
                  className="w-full px-4 py-3 border-2 border-purple-200 rounded-lg focus:border-purple-500 focus:outline-none transition"
                  onKeyPress={(e) => e.key === 'Enter' && handleReserve()}
                />
              </div>

              {/* Bouton Réserver */}
              <button
                onClick={handleReserve}
                disabled={isProcessing}
                className="w-full bg-gradient-to-r from-purple-600 to-pink-600 text-white font-bold py-4 rounded-lg hover:shadow-lg transform hover:scale-105 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isProcessing ? '⏳ Traitement...' : '🚀 Réserver Maintenant'}
              </button>

              {/* Zone de messages */}
              {message && (
                <div className={`mt-6 p-4 rounded-lg border-l-4 flex items-start gap-3 ${
                  reservationResult?.action === 'FAILED'
                    ? 'bg-red-50 border-red-400'
                    : 'bg-green-50 border-green-400'
                }`}>
                  {getMessageIcon()}
                  <div>
                    <p className={`font-semibold ${
                      reservationResult?.action === 'FAILED' ? 'text-red-800' : 'text-green-800'
                    }`}>
                      {message}
                    </p>
                    {reservationResult?.alternative && (
                      <p className="text-sm text-gray-600 mt-1">
                        📍 {reservationResult.alternative.reason}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Résumé du jour */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl shadow-lg p-6 border border-pink-100 sticky top-6">
              <h3 className="text-xl font-bold text-gray-800 mb-4">Planning du {selectedDate}</h3>
              
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {dayReservations.map((slot) => (
                  <div
                    key={slot.time}
                    className={`p-3 rounded-lg transition ${
                      slot.available > 0
                        ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-l-4 border-green-500'
                        : 'bg-gradient-to-r from-red-50 to-pink-50 border-l-4 border-red-500'
                    }`}
                  >
                    <div className="flex justify-between items-center">
                      <span className="font-semibold text-gray-700">{slot.time}</span>
                      <span className={`text-sm font-bold ${
                        slot.available > 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {slot.available}/{slot.capacity}
                      </span>
                    </div>
                    <div className="mt-1 w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-gradient-to-r from-purple-500 to-pink-500 h-2 rounded-full transition-all"
                        style={{ width: `${((slot.capacity - slot.available) / slot.capacity) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}