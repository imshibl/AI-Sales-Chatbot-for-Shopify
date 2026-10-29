import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
const API = `${API_BASE}/api/v1`

type PaymentDetails = {
  order_id: string
  payment_reference: string
  payment_status: 'pending' | 'paid' | 'failed' | 'cancelled'
  order_status: string
  amount: number
  currency: string
  items: { product_id: string; product_name: string; quantity: number; line_total: number }[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = payload?.detail
    throw new Error(typeof detail === 'string' ? detail : detail?.message || `Request failed (${response.status})`)
  }
  return payload as T
}

function money(amount: number, currency: string) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(amount)
}

export const Route = createFileRoute('/payment/$reference')({
  component: DemoPaymentPage,
})

function DemoPaymentPage() {
  const { reference } = Route.useParams()
  const [payment, setPayment] = useState<PaymentDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function loadPayment() {
    setError('')
    try {
      const details = await request<PaymentDetails>(`/demo/payments/${encodeURIComponent(reference)}`)
      setPayment(details)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load this demo payment.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadPayment()
  }, [reference])

  async function completePayment(outcome: 'paid' | 'failed' | 'pending') {
    if (!payment) return
    setError('')
    setBusy(true)
    try {
      const result = await request<Pick<PaymentDetails, 'order_id' | 'payment_status' | 'order_status'>>(
        `/demo/payments/${encodeURIComponent(payment.order_id)}/complete`,
        { method: 'POST', body: JSON.stringify({ outcome }) },
      )
      setPayment((current) => current ? {
        ...current,
        payment_status: result.payment_status,
        order_status: result.order_status,
      } : current)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not update the demo payment.')
    } finally {
      setBusy(false)
    }
  }

  const isPaid = payment?.payment_status === 'paid'
  const isFailed = payment?.payment_status === 'failed' || payment?.payment_status === 'cancelled'

  return (
    <main className="payment-page">
      <section className="payment-card">
        <a className="payment-brand" href="/">thai naturals <span>· demo checkout</span></a>
        {loading ? <div className="payment-message"><span className="payment-spinner" /><p>Loading your demo payment…</p></div> : error && !payment ? (
          <div className="payment-message payment-error"><h1>Payment link unavailable</h1><p>{error}</p><a className="button button-dark" href="/">Return to chat</a></div>
        ) : payment ? (
          <>
            <div className={`payment-state-icon ${isPaid ? 'success' : isFailed ? 'failed' : ''}`}>{isPaid ? '✓' : isFailed ? '!' : '₹'}</div>
            <div className="eyebrow">THAI NATURALS DEMO PAYMENT</div>
            <h1>{isPaid ? 'Payment complete' : isFailed ? 'Payment failed' : 'Complete your payment'}</h1>
            <p className="payment-lead">
              {isPaid
                ? 'Your demo payment is confirmed. Return to the assistant and say “I’ve paid” to verify your order.'
                : isFailed
                  ? 'This demo payment attempt failed. You can retry below, or return to the assistant and ask for the payment link again.'
                  : 'Review your order and choose a demo outcome. No real payment will be collected.'}
            </p>
            <div className="payment-order-meta"><span>Order <strong>{payment.order_id}</strong></span><span>Payment <strong className="payment-status-label">{payment.payment_status}</strong></span></div>
            <div className="payment-items">
              {payment.items.map((item) => (
                <div className="summary-line" key={item.product_id}>
                  <span>{item.product_name} <small>× {item.quantity}</small></span>
                  <strong>{money(item.line_total, payment.currency)}</strong>
                </div>
              ))}
            </div>
            <div className="payment-amount"><span>Total due</span><strong>{money(payment.amount, payment.currency)}</strong></div>
            {error && <p className="payment-inline-error" role="alert">{error}</p>}
            {!isPaid && (
              <div className="payment-demo-actions">
                {isFailed && <button className="button button-outline" onClick={() => void completePayment('pending')} disabled={busy}>Try again</button>}
                {(!isFailed || payment.payment_status === 'pending') && (
                  <>
                    <button className="button button-dark" onClick={() => void completePayment('paid')} disabled={busy}>
                      {busy ? 'Processing…' : 'Simulate successful payment'}
                    </button>
                    <button className="button button-outline" onClick={() => void completePayment('failed')} disabled={busy}>
                      Simulate payment failure
                    </button>
                  </>
                )}
              </div>
            )}
            {isPaid && <div className="payment-success-note">Order status: <strong>{payment.order_status.replaceAll('_', ' ')}</strong></div>}
            <a className="payment-return-link" href="/">Return to AI chat to verify payment →</a>
            <p className="payment-demo-disclaimer">Demo only · This page simulates payment and does not collect or process money.</p>
          </>
        ) : null}
      </section>
    </main>
  )
}
