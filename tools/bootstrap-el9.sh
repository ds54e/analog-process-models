#!/usr/bin/env bash
# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

apm_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
apm_state_dir="${APM_STATE_DIR:-${apm_repo_root}/.apm}"
apm_cache_dir="${apm_state_dir}/cache"
apm_source_dir="${apm_cache_dir}/sources"
apm_build_dir="${apm_cache_dir}/build"
apm_toolchain_dir="${APM_TOOLCHAIN_DIR:-${apm_state_dir}/toolchain}"
apm_jobs="${APM_BUILD_JOBS:-$(getconf _NPROCESSORS_ONLN)}"

apm_ngspice_version="47"
apm_ngspice_url="https://sourceforge.net/projects/ngspice/files/ng-spice-rework/47/ngspice-47.tar.gz/download"
apm_ngspice_sha256="894e649651f1838a14095e5a5439e7d3aa63e87ede14d283173fda4fcdef675f"

apm_openvaf_tag="v24.0.2mob"
apm_openvaf_commit="fdf2522b70f42793f64b1c72f0195c96dea0cc19"
apm_openvaf_url="https://github.com/OpenVAF/OpenVAF-Reloaded.git"

apm_rust_version="1.98.0"
apm_rustup_version="1.29.1"
apm_rustup_url="https://static.rust-lang.org/rustup/archive/${apm_rustup_version}/x86_64-unknown-linux-gnu/rustup-init"
apm_rustup_sha256="dda7234360b7f578ca8b0ddcb80145646fa61a67c1720a5abc7051b35c9fcb71"

apm_alma_vault="https://vault.almalinux.org/9.7/AppStream/x86_64/os/Packages"
apm_llvm_rpms=(
  "llvm-libs-20.1.8-3.el9.x86_64.rpm"
  "llvm-20.1.8-3.el9.x86_64.rpm"
  "llvm-devel-20.1.8-3.el9.x86_64.rpm"
  "clang-resource-filesystem-20.1.8-3.el9.x86_64.rpm"
  "clang-libs-20.1.8-3.el9.x86_64.rpm"
  "clang-20.1.8-3.el9.x86_64.rpm"
)
apm_llvm_sha256=(
  "b6a6a425c928efc3fc1112c2e1f83d1de207b1cfa6eabe6778cac915cd88b491"
  "11603a26363922221c43e73e8e659bd3369b4ef1b186db5ba8f7e4fcf2777729"
  "2ea936ef03a480a5d9968274516714a62ec4d7053676d7cb7dc762513b70d017"
  "c09df5e5ed78e13fa26ff522c95cd65dff52b49bcfde3e9f9550d5ba4868c205"
  "f77ad75f5b9b02cbf170269f3014c033ef42bc5221f7043f32db1ada92227c05"
  "5ab815f68133862e4f5d7e5003bc4982ae6e5f246a604ce9cdc5ba1b1a80a73f"
)

apm_die() {
  echo "bootstrap-el9: $*" >&2
  exit 1
}

apm_require() {
  command -v "$1" >/dev/null 2>&1 || apm_die "required command not found: $1"
}

apm_check_sha256() {
  local apm_file="$1"
  local apm_expected="$2"
  local apm_actual
  apm_actual="$(sha256sum "${apm_file}" | awk '{print $1}')"
  [[ "${apm_actual}" == "${apm_expected}" ]] || \
    apm_die "SHA-256 mismatch for ${apm_file}: expected ${apm_expected}, got ${apm_actual}"
}

apm_download() {
  local apm_url="$1"
  local apm_output="$2"
  local apm_expected="$3"
  local apm_partial="${apm_output}.part"

  if [[ -f "${apm_output}" ]]; then
    apm_check_sha256 "${apm_output}" "${apm_expected}"
    return
  fi
  curl -fL --retry 3 --output "${apm_partial}" "${apm_url}"
  apm_check_sha256 "${apm_partial}" "${apm_expected}"
  mv "${apm_partial}" "${apm_output}"
}

apm_require awk
apm_require autoconf
apm_require automake
apm_require bison
apm_require cpio
apm_require curl
apm_require flex
apm_require gcc
apm_require g++
apm_require git
apm_require make
apm_require rpm2cpio
apm_require sha256sum
apm_require tar

[[ "$(uname -m)" == "x86_64" ]] || apm_die "v2.0 reference bootstrap requires x86_64"
[[ -r /etc/os-release ]] || apm_die "cannot inspect /etc/os-release"
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID_LIKE:-}" == *rhel* || "${ID:-}" == "almalinux" ]] || \
  apm_die "v2.0 reference bootstrap requires RHEL-compatible EL9"
[[ "${VERSION_ID%%.*}" == "9" ]] || apm_die "v2.0 reference bootstrap requires EL9"

mkdir -p "${apm_source_dir}" "${apm_build_dir}" "${apm_toolchain_dir}"

apm_ngspice_archive="${apm_source_dir}/ngspice-47.tar.gz"
apm_ngspice_source="${apm_build_dir}/ngspice-47"
apm_ngspice_build="${apm_build_dir}/ngspice-47-build"
apm_ngspice_prefix="${apm_toolchain_dir}/ngspice-47"
apm_download "${apm_ngspice_url}" "${apm_ngspice_archive}" "${apm_ngspice_sha256}"
if [[ ! -d "${apm_ngspice_source}" ]]; then
  tar -xzf "${apm_ngspice_archive}" -C "${apm_build_dir}"
fi
mkdir -p "${apm_ngspice_build}"
if [[ ! -f "${apm_ngspice_build}/Makefile" ]]; then
  (
    cd "${apm_ngspice_build}"
    "${apm_ngspice_source}/configure" \
      --prefix="${apm_ngspice_prefix}" \
      --enable-predictor \
      --enable-osdi \
      --with-x=no \
      --with-readline=no \
      --disable-debug
  )
fi
make -C "${apm_ngspice_build}" -j "${apm_jobs}"
make -C "${apm_ngspice_build}" install

apm_llvm_root="${apm_toolchain_dir}/llvm20-root"
apm_llvm_prefix="${apm_llvm_root}/usr/lib64/llvm20"
mkdir -p "${apm_llvm_root}"
for apm_index in "${!apm_llvm_rpms[@]}"; do
  apm_rpm_name="${apm_llvm_rpms[${apm_index}]}"
  apm_rpm_path="${apm_source_dir}/${apm_rpm_name}"
  apm_rpm_marker="${apm_llvm_root}/.${apm_rpm_name}.extracted"
  apm_download \
    "${apm_alma_vault}/${apm_rpm_name}" \
    "${apm_rpm_path}" \
    "${apm_llvm_sha256[${apm_index}]}"
  if [[ ! -f "${apm_rpm_marker}" ]]; then
    (
      cd "${apm_llvm_root}"
      rpm2cpio "${apm_rpm_path}" | cpio -idmu --quiet
    )
    touch "${apm_rpm_marker}"
  fi
done
"${apm_llvm_prefix}/bin/llvm-config" --version | grep -Eq '^20\.1\.' || \
  apm_die "the pinned LLVM 20 toolchain did not extract correctly"

apm_rustup_init="${apm_source_dir}/rustup-init"
apm_rustup_dir="${apm_toolchain_dir}/rustup"
apm_cargo_dir="${apm_toolchain_dir}/cargo"
apm_download "${apm_rustup_url}" "${apm_rustup_init}" "${apm_rustup_sha256}"
chmod 0755 "${apm_rustup_init}"
if [[ ! -x "${apm_cargo_dir}/bin/rustup" ]]; then
  RUSTUP_HOME="${apm_rustup_dir}" CARGO_HOME="${apm_cargo_dir}" \
    "${apm_rustup_init}" -y --no-modify-path --profile minimal \
    --default-toolchain "${apm_rust_version}"
fi
RUSTUP_HOME="${apm_rustup_dir}" CARGO_HOME="${apm_cargo_dir}" \
  "${apm_cargo_dir}/bin/rustup" toolchain install "${apm_rust_version}" --profile minimal

apm_openvaf_source="${apm_source_dir}/OpenVAF-Reloaded-${apm_openvaf_tag}"
if [[ ! -d "${apm_openvaf_source}/.git" ]]; then
  git clone --filter=blob:none "${apm_openvaf_url}" "${apm_openvaf_source}"
  git -C "${apm_openvaf_source}" checkout --detach "${apm_openvaf_commit}"
fi
[[ "$(git -C "${apm_openvaf_source}" rev-parse HEAD)" == "${apm_openvaf_commit}" ]] || \
  apm_die "existing OpenVAF source is not the pinned commit ${apm_openvaf_commit}"

apm_build_path="${apm_cargo_dir}/bin:${apm_llvm_prefix}/bin:${apm_llvm_root}/usr/bin:/usr/local/bin:/usr/bin:/bin"
apm_llvm_lib_path="${apm_llvm_prefix}/lib64:${apm_llvm_root}/usr/lib64:/usr/lib64"
(
  cd "${apm_openvaf_source}"
  RUSTUP_HOME="${apm_rustup_dir}" \
  CARGO_HOME="${apm_cargo_dir}" \
  LLVM_SYS_201_PREFIX="${apm_llvm_prefix}" \
  LD_LIBRARY_PATH="${apm_llvm_lib_path}" \
  PATH="${apm_build_path}" \
    "${apm_cargo_dir}/bin/cargo" build --locked --release \
      -p openvaf-driver --features llvm20 -j "${apm_jobs}"
)

apm_openvaf_prefix="${apm_toolchain_dir}/openvaf-${apm_openvaf_tag}"
mkdir -p "${apm_openvaf_prefix}/bin"
install -m 0755 \
  "${apm_openvaf_source}/target/release/openvaf-r" \
  "${apm_openvaf_prefix}/bin/openvaf-r"

"${apm_ngspice_prefix}/bin/ngspice" --version
LD_LIBRARY_PATH="${apm_llvm_lib_path}" \
  "${apm_openvaf_prefix}/bin/openvaf-r" --version

echo "APM toolchain bootstrap complete"
echo "ngspice: ${apm_ngspice_prefix}/bin/ngspice"
echo "OpenVAF-ReLoaded: ${apm_openvaf_prefix}/bin/openvaf-r"
echo "State directory: ${apm_state_dir}"
