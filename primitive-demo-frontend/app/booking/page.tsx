'use client';

import { useMemo, useState } from 'react';

type Message = {
  role: 'user' | 'assistant';
  content: string;
};

type Flight = {
  option: number;
  price_usd?: string | number;
  outbound_stops?: number;
  outbound_duration_min?: number | string;
  inbound_stops?: number;
  inbound_duration_min?: number | string;
  carry_on_bags?: number;
  checked_bags?: number;
  booking_url?: string;
  outbound_legs?: any[];
  inbound_legs?: any[];
};

function fmtDuration(value: unknown) {
  const minutes = Number(value);
  if (!Number.isFinite(minutes)) return value ? String(value) : '';
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

export default function BookingPage() {
  const [input, setInput] = useState('Find a one-way flight from SEA to JFK on 2026-06-12 for 1 adult');
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Tell me the route, date, trip type, and passengers. I can search Kiwi flights and then guide the booking form.'
    }
  ]);
  const [history, setHistory] = useState<Array<{ role: string; content: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [bookingResult, setBookingResult] = useState<any>(null);
  const [session, setSession] = useState<any>(null);
  const [collected, setCollected] = useState<Record<string, any>>({});

  const flights: Flight[] = useMemo(() => {
    return bookingResult?.api_result?.flights || bookingResult?.flights || [];
  }, [bookingResult]);

  async function callBooking(body: Record<string, any>) {
    const res = await fetch('/api/booking', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || data.detail || 'Booking request failed');
    return data;
  }

  async function send() {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((m) => [...m, { role: 'user', content: text }]);
    setInput('');
    setLoading(true);

    try {
      if (session?.session_id) {
        const data = await callBooking({
          action: 'session_message',
          session_id: session.session_id,
          message: text
        });
        setSession(data);
        setCollected(data.collected || {});
        setMessages((m) => [...m, { role: 'assistant', content: data.answer || 'Booking page updated.' }]);
        return;
      }

      const data = await callBooking({ action: 'invoke', query: text, history });
      setBookingResult(data);
      const answer = data.answer || 'The booking primitive completed the request.';
      setMessages((m) => [...m, { role: 'assistant', content: answer }]);
      setHistory((h) => [...h, { role: 'user', content: text }, { role: 'assistant', content: answer }]);
    } catch (e: any) {
      setMessages((m) => [...m, { role: 'assistant', content: String(e.message || e) }]);
    } finally {
      setLoading(false);
    }
  }

  async function startBooking(flight: Flight) {
    if (!flight.booking_url || loading) return;
    setLoading(true);
    setMessages((m) => [...m, { role: 'user', content: `Book option ${flight.option}` }]);
    try {
      const data = await callBooking({
        action: 'open_session',
        booking_url: flight.booking_url,
        headless: true
      });
      setSession(data);
      setCollected(data.collected || {});
      setMessages((m) => [...m, { role: 'assistant', content: data.answer || 'Booking page opened.' }]);
    } catch (e: any) {
      setMessages((m) => [...m, { role: 'assistant', content: String(e.message || e) }]);
    } finally {
      setLoading(false);
    }
  }

  async function continueBooking() {
    if (!session?.session_id || loading) return;
    setLoading(true);
    try {
      const data = await callBooking({ action: 'continue_session', session_id: session.session_id });
      setSession(data);
      setCollected(data.collected || {});
      setMessages((m) => [...m, { role: 'assistant', content: data.answer || 'Continued booking flow.' }]);
    } catch (e: any) {
      setMessages((m) => [...m, { role: 'assistant', content: String(e.message || e) }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container wide">
      <div className="bookingLayout">
        <section className="panel">
          <div className="panelHead">Kiwi Booking Chat</div>
          <div className="messages">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role === 'user' ? 'user' : 'assistant'}`}>
                {m.content}
              </div>
            ))}
            {loading && <div className="msg assistant">Working...</div>}
          </div>
          <div className="inputbar">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') send();
              }}
              placeholder={session?.session_id ? 'Reply with passenger details...' : 'Search flights...'}
            />
            <button onClick={send} disabled={loading}>{loading ? '...' : 'Send'}</button>
          </div>
        </section>

        <aside className="panel">
          <div className="panelHead">Flight Options</div>
          <div className="bookingSide">
            {!bookingResult ? (
              <p className="muted">Search results will appear here.</p>
            ) : flights.length === 0 ? (
              <pre className="raw">{JSON.stringify(bookingResult.extracted_args || bookingResult, null, 2)}</pre>
            ) : (
              flights.map((f) => (
                <div className="flightCard" key={f.option}>
                  <div className="flightTop">
                    <b>Option {f.option}</b>
                    <span>${f.price_usd || 'N/A'}</span>
                  </div>
                  <div className="muted">
                    Outbound: {f.outbound_stops ?? 0} stop(s), {fmtDuration(f.outbound_duration_min)}
                  </div>
                  {f.inbound_duration_min ? (
                    <div className="muted">
                      Return: {f.inbound_stops ?? 0} stop(s), {fmtDuration(f.inbound_duration_min)}
                    </div>
                  ) : null}
                  <div className="muted">Carry-on: {f.carry_on_bags ?? 0} | Checked: {f.checked_bags ?? 0}</div>
                  <button className="primaryBtn" onClick={() => startBooking(f)} disabled={!f.booking_url || loading}>
                    Book This Option
                  </button>
                </div>
              ))
            )}
          </div>
        </aside>

        <aside className="panel">
          <div className="panelHead">Live Booking Session</div>
          <div className="bookingSide">
            {!session ? (
              <p className="muted">Choose a flight option to open the Kiwi checkout flow.</p>
            ) : (
              <>
                <div className="traceItem">
                  <div className="traceTop">
                    <b>Session</b>
                    <span className="badge done">{session.status?.step || 'open'}</span>
                  </div>
                  <div className="raw">{session.session_id}</div>
                </div>
                {session.question?.question ? (
                  <div className="traceItem">
                    <b>Next Question</b>
                    <div className="raw">{session.question.question}</div>
                  </div>
                ) : null}
                <div className="traceItem">
                  <b>Collected</b>
                  <pre className="raw">{JSON.stringify(collected, null, 2)}</pre>
                </div>
                {session.status?.screenshot_url ? (
                  <img className="bookingShot" src={session.status.screenshot_url} alt="Kiwi booking page screenshot" />
                ) : null}
                <button className="primaryBtn" onClick={continueBooking} disabled={loading}>
                  Continue
                </button>
              </>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
