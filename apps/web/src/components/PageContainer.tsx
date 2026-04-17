import { ReactNode } from 'react';

type PageContainerProps = {
  children: ReactNode;
};

export default function PageContainer({ children }: PageContainerProps) {
  return (
    <div className="project-content">
      <div className="module-viewport">
        <div className="module-panel">{children}</div>
      </div>
    </div>
  );
}

