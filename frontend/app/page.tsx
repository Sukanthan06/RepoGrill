import { StartForm } from "@/components/StartForm";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-8 px-6 py-12">
      <div>
        <h1 className="text-4xl font-bold tracking-tight">RepoGrill</h1>
        <p className="mt-3 text-zinc-400">Get grilled on your own code.</p>
      </div>
      <StartForm />
    </main>
  );
}
