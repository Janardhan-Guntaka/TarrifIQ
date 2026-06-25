import Link from "next/link";
import { SiteHeader } from "@/components/SiteHeader";
import { Disclaimer } from "@/components/Disclaimer";
import { APP_NAME } from "@/lib/constants";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-blue-50/30">
      <SiteHeader />

      <main>
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-4 pb-16 pt-16 sm:px-6 sm:pt-24">
          <div className="max-w-3xl">
            <p className="mb-4 inline-flex rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-brand">
              AI-powered US import classification
            </p>
            <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl sm:leading-tight">
              Classify HTS codes and estimate duties in seconds—not weeks.
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-slate-600">
              {APP_NAME} helps Shopify sellers and mid-size importers move goods across borders
              faster. Get explainable HTS classifications and duty estimates without waiting on
              a broker for every SKU—or give your broker a head start.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link
                href="/login"
                className="rounded-lg bg-brand px-6 py-3 text-sm font-semibold text-white shadow-md hover:bg-brand-dark"
              >
                Start classifying free
              </Link>
              <a
                href="#how-it-works"
                className="rounded-lg border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                See how it works
              </a>
            </div>
          </div>
        </section>

        {/* Problem */}
        <section className="border-y border-slate-200 bg-white py-16">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 className="text-2xl font-bold text-slate-900">The problem</h2>
            <p className="mt-3 max-w-2xl text-slate-600">
              Importing into the US means navigating thousands of HTS lines, layered tariffs
              (Section 301, IEEPA, FTAs), and constant revisions. For growing brands:
            </p>
            <ul className="mt-8 grid gap-6 sm:grid-cols-3">
              {[
                {
                  title: "Slow broker queues",
                  body: "Every new product waits days for classification before you can price landed cost.",
                },
                {
                  title: "Opaque duty math",
                  body: "Spreadsheets and guesswork lead to margin surprises at customs.",
                },
                {
                  title: "No audit trail",
                  body: "When rates change, you can't prove what logic you used last quarter.",
                },
              ].map((item) => (
                <li
                  key={item.title}
                  className="rounded-xl border border-slate-200 bg-slate-50 p-5"
                >
                  <h3 className="font-semibold text-slate-900">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{item.body}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* Solution */}
        <section id="how-it-works" className="py-16">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 className="text-2xl font-bold text-slate-900">Our solution</h2>
            <p className="mt-3 max-w-2xl text-slate-600">
              {APP_NAME} combines official HTS data, vector search, and policy engines—rates always
              come from the tariff schedule, not from AI guesses.
            </p>
            <div className="mt-10 grid gap-8 md:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900">For Shopify & importers</h3>
                <ul className="mt-4 space-y-3 text-sm text-slate-600">
                  <li>• Describe a product in plain English—get HTS + duty estimate instantly</li>
                  <li>• Model landed cost before you list a new SKU</li>
                  <li>• Save every query to your account for compliance records</li>
                </ul>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900">For brokers & ops teams</h3>
                <ul className="mt-4 space-y-3 text-sm text-slate-600">
                  <li>• Pre-screen classifications before formal entry</li>
                  <li>• Explainable reasoning with cited HTS release version</li>
                  <li>• Flag low-confidence cases for human review</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="border-t border-slate-200 bg-slate-900 py-16 text-white">
          <div className="mx-auto max-w-6xl px-4 text-center sm:px-6">
            <h2 className="text-2xl font-bold">Ready to classify your next shipment?</h2>
            <p className="mx-auto mt-3 max-w-xl text-slate-300">
              Sign in with Google. Your classification history stays private to your account.
            </p>
            <Link
              href="/login"
              className="mt-8 inline-block rounded-lg bg-white px-8 py-3 text-sm font-semibold text-slate-900 hover:bg-slate-100"
            >
              Sign in with Google
            </Link>
          </div>
        </section>

        <footer className="border-t border-slate-200 bg-white py-10">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <Disclaimer variant="footer" />
            <p className="mt-4 text-xs text-slate-400">© {new Date().getFullYear()} {APP_NAME}</p>
          </div>
        </footer>
      </main>
    </div>
  );
}
