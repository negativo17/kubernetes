%global debug_package %{nil}

%global username kube
%global module kube-proxy kube-apiserver kube-controller-manager kubelet kubeadm kube-scheduler kubectl

Name:           kubernetes
Version:        1.18.4
Release:        1%{?dist}
Summary:        Production-Grade Container Scheduling and Management
License:        ASL 2.0
URL:            https://kubernetes.io

ExclusiveArch:  x86_64 aarch64 ppc64le s390x %{arm}
Source0:        https://github.com/%{name}/%{name}/archive/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

Source101:      kube-proxy.service
Source102:      kube-apiserver.service
Source103:      kube-scheduler.service
Source104:      kube-controller-manager.service
Source105:      kubelet.service

Source106:      environ-apiserver
Source107:      environ-config
Source108:      environ-controller-manager
Source109:      environ-kubelet
Source110:      environ-kubelet.kubeconfig
Source111:      environ-proxy
Source112:      environ-scheduler

Source113:      kubernetes-accounting.conf
Source114:      kubeadm.conf
Source115:      kubernetes.conf

BuildRequires:  go-bindata
BuildRequires:  golang >= 1.2-7
BuildRequires:  rsync
BuildRequires:  systemd

Obsoletes:      cadvisor <= %{version}-%{release}

# This is a metapackage in Fedora that pulls in these two, keep to have an
# upgrade path.
Requires:       kubernetes-master = %{version}-%{release}
Requires:       kubernetes-node = %{version}-%{release}

%description
Kubernetes is an open source system for managing containerized applications
across multiple hosts. It provides basic mechanisms for deployment,
maintenance, and scaling of applications.

Kubernetes builds upon a decade and a half of experience at Google running
production workloads at scale using a system called Borg, combined with
best-of-breed ideas and practices from the community.

%package common
Summary:        Common data for Kubernetes services

Requires(pre):  shadow-utils

%description common
Common files and configuration for Kubernetes master and nodes

%package master
Summary:        Kubernetes services for master host

Requires:       kubernetes-common = %{version}-%{release}
# If master is installed with node, version and release must be the same
Conflicts:      kubernetes-node < %{version}-%{release}
Conflicts:      kubernetes-node > %{version}-%{release}

%description master
Kubernetes services for master host

%package node
Summary:        Kubernetes services for node host

Requires:       kubernetes-common = %{version}-%{release}
Requires:       (docker or docker-ce or moby-engine or cri-o)
Requires:       conntrack-tools
Requires:       socat

# if master is installed with node, version and release must be the same
Conflicts:      kubernetes-master < %{version}-%{release}
Conflicts:      kubernetes-master > %{version}-%{release}

%description node
Kubernetes services for node host

%package  kubeadm
Summary:        Kubernetes tool for standing up clusters

Requires:       kubernetes-node = %{version}-%{release}
Requires:       containernetworking-plugins

%description kubeadm
Kubernetes tool for standing up clusters.

%package client
Summary:        Kubernetes client tools

%description client
Kubernetes client tools like kubectl.

%prep
%autosetup

# src/k8s.io/kubernetes/pkg/util/certificates
# Patch the code to remove eliptic.P224 support
# For whatever reason:
# https://groups.google.com/forum/#!topic/Golang-nuts/Oq4rouLEvrU
for dir in vendor/github.com/google/certificate-transparency/go/x509 pkg/util/certificates; do
  if [ -d "${dir}" ]; then
    pushd ${dir}
    sed -i "/^[^=]*$/ s/oidNamedCurveP224/oidNamedCurveP256/g" *.go
    sed -i "/^[^=]*$/ s/elliptic\.P224/elliptic.P256/g" *.go
    popd
  fi
done

%build
# Parallel building breaks
make

%install
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_datadir}/bash-completion/completions/
mkdir -p %{buildroot}%{_mandir}/man1/
mkdir -p %{buildroot}%{_sharedstatedir}/kubelet
mkdir -p %{buildroot}%{_sysconfdir}/%{name}/manifests
mkdir -p %{buildroot}%{_prefix}/lib/systemd/system.conf.d
mkdir -p %{buildroot}%{_unitdir}/kubelet.service.d
mkdir -p %{buildroot}%{_tmpfilesdir}
mkdir -p %{buildroot}%{_unitdir}
mkdir -p %{buildroot}/run/%{name}/

# Binaries
for binary in %{module}; do
    install -p -m 755 _output/local/go/bin/$binary %{buildroot}%{_bindir}/
done

# Service data
install -p -m 0644 %{SOURCE114} %{buildroot}/%{_unitdir}/kubelet.service.d/
install -p -m 0644 %{SOURCE113} %{buildroot}/%{_prefix}/lib/systemd/system.conf.d/
install -p -m 0644 %{SOURCE115} %{buildroot}/%{_tmpfilesdir}/

for unit in %{SOURCE101} %{SOURCE102} %{SOURCE103} %{SOURCE104} %{SOURCE105}; do
    install -p -m 0644 $unit %{buildroot}%{_unitdir}/
done

for envfile in %{SOURCE106} %{SOURCE107} %{SOURCE108} %{SOURCE109} %{SOURCE110} %{SOURCE111} %{SOURCE112}; do
   install -p -m 644 $envfile -T %{buildroot}%{_sysconfdir}/%{name}/$(echo -n $envfile |sed 's/.*environ-//g')
done

# Bash completion
%{buildroot}%{_bindir}/kubectl completion bash > %{buildroot}%{_datadir}/bash-completion/completions/kubectl

# Generate man pages
for binary in %{module}; do
    _output/local/go/bin/genman %{buildroot}%{_mandir}/man1/ $binary
done

%check
if [ 1 != 1 ]; then
hack/test-cmd.sh
hack/benchmark-go.sh
hack/test-go.sh
hack/test-integration.sh --use_go_build
fi

%pre common
getent group %{username} >/dev/null || groupadd -r %{username} &>/dev/null || :
getent passwd %{username} >/dev/null || useradd -r -s /sbin/nologin \
  -d / -c "Kubernetes" -g %{username} %{username} &>/dev/null || :
exit 0

%post master
%systemd_post kube-apiserver.service kube-scheduler.service kube-controller-manager.service

%preun master
%systemd_preun kube-apiserver.service kube-scheduler.service kube-controller-manager.service

%postun master
%systemd_postun kube-apiserver.service kube-scheduler.service kube-controller-manager.service

%post node
%systemd_post kubelet.service kube-proxy.service
# If accounting is not currently enabled reexec systemd
if [[ `systemctl show docker kubelet | grep -q -e CPUAccounting=no -e MemoryAccounting=no; echo $?` -eq 0 ]]; then
  systemctl daemon-reexec
fi

%preun node
%systemd_preun kubelet.service kube-proxy.service

%postun node
%systemd_postun kubelet.service kube-proxy.service

%files
# Metapackage depending on master and node

%files common
%license LICENSE
%doc README.md SUPPORT.md CHANGELOG/CHANGELOG*.md
%dir %{_sysconfdir}/%{name}
%config(noreplace) %{_sysconfdir}/%{name}/config
%{_tmpfilesdir}/kubernetes.conf
%verify(not size mtime md5) %attr(755,kube,kube) %dir /run/%{name}

%files master
%attr(754,-,kube) %caps(cap_net_bind_service=ep) %{_bindir}/kube-apiserver
%{_bindir}/kube-controller-manager
%{_bindir}/kube-scheduler
%{_mandir}/man1/kube-apiserver.*
%{_mandir}/man1/kube-controller-manager.*
%{_mandir}/man1/kube-scheduler.*
%{_unitdir}/kube-apiserver.service
%{_unitdir}/kube-controller-manager.service
%{_unitdir}/kube-scheduler.service
%config(noreplace) %{_sysconfdir}/%{name}/apiserver
%config(noreplace) %{_sysconfdir}/%{name}/config
%config(noreplace) %{_sysconfdir}/%{name}/controller-manager
%config(noreplace) %{_sysconfdir}/%{name}/scheduler

%files node
%{_bindir}/kubelet
%{_bindir}/kube-proxy
%{_mandir}/man1/kubelet.*
%{_mandir}/man1/kube-proxy.*
%{_unitdir}/kube-proxy.service
%{_unitdir}/kubelet.service
%{_prefix}/lib/systemd/system.conf.d/kubernetes-accounting.conf
%dir %{_sharedstatedir}/kubelet
%dir %{_sysconfdir}/%{name}/manifests
%config(noreplace) %{_sysconfdir}/%{name}/kubelet
%config(noreplace) %{_sysconfdir}/%{name}/kubelet.kubeconfig
%config(noreplace) %{_sysconfdir}/%{name}/proxy

%files kubeadm
%{_bindir}/kubeadm
%{_mandir}/man1/kubeadm.1*
%{_mandir}/man1/kubeadm-*
%{_unitdir}/kubelet.service.d/kubeadm.conf

%files client
%license LICENSE
%doc README.md SUPPORT.md CHANGELOG/CHANGELOG*.md
%{_bindir}/kubectl
%{_mandir}/man1/kubectl.1*
%{_mandir}/man1/kubectl-*
%{_datadir}/bash-completion/completions/kubectl

%changelog
* Tue Jun 23 2020 Simone Caronni <negativo17@gmail.com> - 1.18.4-1
- Update to 1.18.4.

* Wed May 27 2020 Simone Caronni <negativo17@gmail.com> - 1.18.3-1
- Update to 1.18.3.

* Thu May 07 2020 Simone Caronni <negativo17@gmail.com> - 1.18.2-1
- First build based off Fedora packages.
- Simplify SPEC file massively.
- Move daemon common components in common subpackage.
- Do not require client installation on master and nodes.
- Update systemd units.
