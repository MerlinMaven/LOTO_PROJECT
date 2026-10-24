import { Link } from "react-router-dom";

interface SmartLotoLogoProps {
  /**
   * Classe Tailwind contrôlant l'échelle du logo.
   * - 'h-12' -> 48px
   * - 'h-14' -> 56px (largeur ~186px)
   * - 'h-16' -> 64px (largeur ~212px, plein impact)
   * - 'h-20' -> 80px (très grand format)
   */
  sizeClassName?: string;
}

export function SmartLotoLogo({ sizeClassName = "h-16" }: SmartLotoLogoProps) {
  return (
    <Link
      to="/procedures"
      className="group flex flex-col items-center justify-center w-full gap-2 select-none focus:outline-none text-center"
      title="SmartLOTO - Console de validation HSE"
    >
      <div className="flex items-center justify-center w-full">
        <img
          src="/logo-smartloto.png"
          alt="SmartLOTO Logo"
          className={`${sizeClassName} w-auto max-w-[200px] object-contain mx-auto transition-transform duration-200 group-hover:scale-[1.02]`}
        />
      </div>
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400 text-center w-full">
        Console de validation HSE
      </p>
    </Link>
  );
}
