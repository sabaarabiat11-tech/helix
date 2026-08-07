import { useOutletContext } from "react-router-dom";
import Topbar from "./Topbar";

export default function PageShell({ title, subtitle, right, hasHero = false, children }) {
  const { onMenuClick } = useOutletContext();
  return (
    <div className="min-h-screen flex flex-col">
      <Topbar title={title} subtitle={subtitle} onMenuClick={onMenuClick} right={right} titleAsHeading={!hasHero} />
      <main className="flex-1 px-4 lg:px-6 py-6 max-w-[1400px] w-full mx-auto">{children}</main>
    </div>
  );
}
