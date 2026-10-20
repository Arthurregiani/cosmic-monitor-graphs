## Instalação sem compilação / Prebuilt installation

Pacote para **amd64 (Intel/AMD 64 bits), Pop!_OS 24.04 com COSMIC**. A base Ubuntu 24.04 define os requisitos de bibliotecas; outras distribuições não foram validadas.

1. Baixe `cosmic-monitor-graphs_1.1.0_amd64.deb` abaixo.
2. Na pasta do download, execute:

```sh
sudo apt install ./cosmic-monitor-graphs_1.1.0_amd64.deb
```

Abra **Monitor COSMIC (Gráficos)** no menu de aplicativos. Não é necessário instalar Rust nem compilar. O pacote não substitui o monitor oficial.

Para remover:

```sh
sudo apt remove cosmic-monitor-graphs
```

Se você usava a instalação manual anterior, consulte a seção de migração do README: o atalho do usuário pode ocultar o novo atalho do pacote. As configurações são preservadas.

### Arquivos

- `.deb`: aplicativo compilado e dependências de execução declaradas para o APT.
- `SHA256SUMS`: somas para verificar os downloads com `sha256sum -c SHA256SUMS`.
- `source.tar.xz`: código-fonte completo usado no pacote, modificação, ferramentas e dependências Cargo vendorizadas. Inclui instruções de compilação offline, após instalar o Rust e as bibliotecas de desenvolvimento.

### English

Prebuilt **amd64** package, built on Ubuntu 24.04 for Pop!_OS 24.04 with COSMIC. Download the `.deb` and run the `sudo apt install ./...deb` command above. No Rust toolchain or compilation is needed. The system monitor remains installed separately. This is an unofficial GPL-3.0-only community modification. Full build sources and dependency sources are included in the source archive.
